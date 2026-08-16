"""Sprint 1B speech production regression coverage.

Covers: MiMo ASR/TTS official-contract payloads, provider error classification, audio
artifact validation, TaskJob ASR/TTS pipeline (raw preservation, single adoption,
normalization chain, retry/backoff, empty-transcript handling), TTS text degradation,
AI-call audit redaction + latency, and signed controlled media access URLs.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import time
import uuid
import wave

import pytest
from app.ai.providers.base import (
    AudioReference,
    ProviderFailure,
    ProviderFailureKind,
    SynthesizedAudio,
    TranscriptResult,
    map_provider_error,
)
from app.ai.providers.speech.fake import FakeSpeechProvider
from app.ai.providers.speech.mimo_asr import MiMoASRProvider
from app.ai.providers.speech.mimo_tts import MiMoTTSProvider
from app.ai.providers.speech.mimo_voiceclone import MiMoVoiceCloneProvider
from app.ai.providers.speech.mimo_voicedesign import MiMoVoiceDesignProvider
from app.api.v1.media import get_media_storage
from app.audio.signing import sign_media_url, verify_media_signature
from app.audio.storage import LocalStorageAdapter
from app.audio.validation import AudioValidationError, validate_audio
from app.core.config import Settings
from app.core.enums import AudioPurpose, TaskJobState
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.domain import (
    AICall,
    Answer,
    ASRNormalization,
    ASRTranscript,
    AuditEvent,
    MediaAsset,
    NormalizationMapping,
    TaskJob,
)
from app.services.ai_calls import create_ai_call
from app.services.speech_jobs import (
    enqueue_asr_job,
    enqueue_tts_job,
    process_asr_job,
    process_speech_job,
    process_tts_job,
    tts_fallback_text,
)
from fastapi.testclient import TestClient
from httpx import ConnectTimeout, HTTPStatusError, Request, Response
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def _wav_bytes(duration_frames: int = 8000, rate: int = 8000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * duration_frames)
    return buffer.getvalue()


def _run(coro) -> object:
    return asyncio.run(coro)


def _db_engine():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine


class MemoryStorage:
    def __init__(self) -> None:
        self.contents: dict[str, bytes] = {}

    def store(self, key: str, content: bytes):
        self.contents[key] = content
        from app.audio.storage import StorageRef

        return StorageRef(key=key)

    def read(self, key: str) -> bytes:
        return self.contents[key]

    def exists(self, key: str) -> bool:
        return key in self.contents


class AlwaysFailSpeechProvider:
    provider_name = "FAIL"

    def __init__(self, error: ProviderFailure) -> None:
        self.error = error

    async def transcribe(self, audio: AudioReference) -> TranscriptResult:
        raise self.error

    async def synthesize(self, text: str, voice: str | None = None) -> SynthesizedAudio:
        raise self.error


def test_speech_config_defaults_match_contract(monkeypatch) -> None:
    for name in [
        "MEDIA_STORAGE_DIR",
        "MEDIA_MAX_SIZE_BYTES",
        "MEDIA_ALLOWED_MIME_TYPES",
        "MEDIA_MAX_DURATION_SECONDS",
        "MEDIA_ACCESS_URL_TTL_SECONDS",
        "MEDIA_URL_SECRET",
        "MIMO_ASR_LANGUAGE",
        "MIMO_TTS_VOICE",
    ]:
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)
    assert settings.mimo_asr_language == "auto"
    assert settings.mimo_tts_voice == "mimo_default"
    assert settings.media_max_size_bytes == 20 * 1024 * 1024
    assert "audio/wav" in settings.media_allowed_mime_types
    assert settings.media_access_url_ttl_seconds == 3600


def test_audio_validation_extracts_wav_metadata() -> None:
    content = _wav_bytes()
    metadata = validate_audio(
        AudioReference(content=content, filename="a.wav", mime_type="audio/wav"),
        max_size_bytes=10_000_000,
        allowed_mime_types=["audio/wav", "audio/mpeg"],
        max_duration_seconds=120,
    )
    assert metadata.codec == "pcm"
    assert metadata.sample_rate == 8000
    assert metadata.channels == 1
    assert metadata.duration_ms == 1000
    assert metadata.size_bytes == len(content)
    assert metadata.sha256 == hashlib.sha256(content).hexdigest()


def test_audio_validation_rejects_empty_oversized_and_corrupt() -> None:
    kwargs = {
        "max_size_bytes": 10_000_000,
        "allowed_mime_types": ["audio/wav", "audio/mpeg"],
        "max_duration_seconds": 120,
    }
    with pytest.raises(AudioValidationError):
        validate_audio(AudioReference(content=b"", filename="e.wav", mime_type="audio/wav"), **kwargs)
    with pytest.raises(AudioValidationError):
        validate_audio(AudioReference(content=_wav_bytes(), filename="big.wav", mime_type="audio/wav"), max_size_bytes=10, allowed_mime_types=["audio/wav", "audio/mpeg"], max_duration_seconds=120)
    with pytest.raises(AudioValidationError):
        validate_audio(AudioReference(content=_wav_bytes(), filename="x.txt", mime_type="text/plain"), **kwargs)
    with pytest.raises(AudioValidationError):
        validate_audio(AudioReference(content=b"not a wav at all", filename="bad.wav", mime_type="audio/wav"), **kwargs)


def test_mp3_with_valid_header_passes_validation() -> None:
    id3 = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 32
    metadata = validate_audio(
        AudioReference(content=id3, filename="a.mp3", mime_type="audio/mpeg"),
        max_size_bytes=10_000_000,
        allowed_mime_types=["audio/wav", "audio/mpeg"],
        max_duration_seconds=120,
    )
    assert metadata.codec == "mp3"


def test_provider_error_mapping_classifies_http_errors() -> None:
    request = Request("POST", "https://base/chat/completions")
    auth = HTTPStatusError("401", request=request, response=Response(401, request=request))
    mapped = map_provider_error(auth)
    assert mapped.kind == ProviderFailureKind.PERMANENT
    assert mapped.status_code == 401

    server = HTTPStatusError("500", request=request, response=Response(500, request=request))
    assert map_provider_error(server).kind == ProviderFailureKind.TEMPORARY
    assert map_provider_error(ConnectTimeout("timeout", request=request)).kind == ProviderFailureKind.TEMPORARY


def test_asr_payload_matches_official_contract_and_empty_transcript_is_retryable() -> None:
    captured: list[dict] = []

    async def fake_post(payload):
        captured.append(payload)
        return {"choices": [{"message": {"content": "转写结果"}}]}, "req-asr-1"

    provider = MiMoASRProvider("https://base", "key", "mimo-v2.5-asr", language="zh")
    provider._post = fake_post
    result = _run(provider.transcribe(AudioReference(content=_wav_bytes(), filename="a.wav", mime_type="audio/wav")))
    assert result.text == "转写结果"
    assert result.request_id == "req-asr-1"
    body = captured[0]
    assert body["model"] == "mimo-v2.5-asr"
    assert body["asr_options"] == {"language": "zh"}
    assert "stream" not in body
    content = body["messages"][0]["content"][0]
    assert content["type"] == "input_audio"
    assert content["input_audio"]["data"].startswith("data:audio/wav;base64,")

    async def fake_empty(payload):
        return {"choices": [{"message": {"content": "   "}}]}, "req-empty"

    empty_provider = MiMoASRProvider("https://base", "key", "mimo-v2.5-asr")
    empty_provider._post = fake_empty
    with pytest.raises(ProviderFailure) as exc_info:
        _run(empty_provider.transcribe(AudioReference(content=_wav_bytes(), filename="a.wav", mime_type="audio/wav")))
    assert exc_info.value.code == "EMPTY_TRANSCRIPT"
    assert exc_info.value.kind == ProviderFailureKind.TEMPORARY


def test_tts_payload_matches_official_contract_and_parses_audio() -> None:
    wav_content = _wav_bytes()
    import base64

    captured: list[dict] = []

    async def fake_post(payload):
        captured.append(payload)
        return {
            "choices": [{"message": {"audio": {"data": base64.b64encode(wav_content).decode("ascii")}}}]
        }, "req-tts-1"

    provider = MiMoTTSProvider("https://base", "key", "mimo-v2.5-tts", voice="冰糖")
    provider._post = fake_post
    audio = _run(provider.synthesize("请说明放行流程"))
    assert audio.content == wav_content
    assert audio.mime_type == "audio/wav"
    assert audio.request_id == "req-tts-1"
    body = captured[0]
    assert body["model"] == "mimo-v2.5-tts"
    assert body["audio"] == {"format": "wav", "voice": "冰糖"}
    assert body["messages"][-1] == {"role": "assistant", "content": "请说明放行流程"}
    assert "stream" not in body

    async def fake_no_audio(payload):
        return {"choices": [{"message": {"audio": {}}}]}, "req-empty-audio"

    bad_provider = MiMoTTSProvider("https://base", "key", "mimo-v2.5-tts")
    bad_provider._post = fake_no_audio
    with pytest.raises(ProviderFailure) as exc_info:
        _run(bad_provider.synthesize("x"))
    assert exc_info.value.code == "EMPTY_AUDIO"


def test_voice_capabilities_are_feature_gated_and_contract_correct() -> None:
    design = MiMoVoiceDesignProvider()
    with pytest.raises(ProviderFailure) as exc_info:
        _run(design.design_voice("沉稳专业", "请说明"))
    assert exc_info.value.code == "FEATURE_GATED"

    clone = MiMoVoiceCloneProvider()
    with pytest.raises(ProviderFailure) as exc_info:
        _run(clone.clone_voice("请说明", AudioReference(content=_wav_bytes(), filename="s.wav", mime_type="audio/wav")))
    assert exc_info.value.code == "FEATURE_GATED"

    captured: list[dict] = []

    async def fake_design(payload):
        captured.append(payload)
        return {"choices": [{"message": {"audio": {"data": "AAAA"}}}]}, "req-d"

    enabled_design = MiMoVoiceDesignProvider(enabled=True, base_url="https://base", api_key="key")
    enabled_design._post = fake_design
    _run(enabled_design.design_voice("沉稳专业", "请说明"))
    body = captured[0]
    assert body["model"] == "mimo-v2.5-tts-voicedesign"
    assert body["messages"][0] == {"role": "user", "content": "沉稳专业"}
    assert body["messages"][-1] == {"role": "assistant", "content": "请说明"}
    assert "voice" not in body["audio"]

    async def fake_clone(payload):
        captured.append(payload)
        return {"choices": [{"message": {"audio": {"data": "AAAA"}}}]}, "req-c"

    enabled_clone = MiMoVoiceCloneProvider(enabled=True, base_url="https://base", api_key="key")
    enabled_clone._post = fake_clone
    _run(enabled_clone.clone_voice("请说明", AudioReference(content=_wav_bytes(), filename="s.wav", mime_type="audio/wav")))
    clone_body = captured[-1]
    assert clone_body["model"] == "mimo-v2.5-tts-voiceclone"
    assert clone_body["audio"]["format"] == "wav"
    assert isinstance(clone_body["audio"]["voice"], str) and clone_body["audio"]["voice"]


def test_asr_job_pipeline_preserves_raw_and_chains_normalization() -> None:
    engine = _db_engine()
    with Session(engine) as session:
        answer = Answer(attempt_item_id=uuid.uuid4(), answer_type="MAIN")
        session.add(answer)
        session.flush()
        storage = MemoryStorage()
        storage.store("answers/key.wav", _wav_bytes())
        job = enqueue_asr_job(
            session,
            answer_id=answer.id,
            storage_key="answers/key.wav",
            filename="key.wav",
            mime_type="audio/wav",
            business_key=f"asr-{answer.id}",
            max_retries=1,
        )
        session.commit()

        processed = _run(process_asr_job(session, job, FakeSpeechProvider("B七三七NG 维修放心"), storage))
        session.commit()

        assert processed.state == TaskJobState.SUCCEEDED.value
        assert processed.completed_at is not None
        transcripts = list(session.scalars(select(ASRTranscript).where(ASRTranscript.answer_id == answer.id)))
        assert len(transcripts) == 1
        transcript = transcripts[0]
        assert transcript.raw_text == "B七三七NG 维修放心"
        assert transcript.is_adopted is True
        assert transcript.adopted_at is not None
        assert transcript.raw_response == {"text": "B七三七NG 维修放心"}

        normalization = session.scalar(select(ASRNormalization).where(ASRNormalization.transcript_id == transcript.id))
        assert normalization.normalized_text == "B737NG 维修放行"
        mappings = list(session.scalars(select(NormalizationMapping).where(NormalizationMapping.normalization_id == normalization.id)))
        assert any(m.raw_fragment == "B七三七NG" for m in mappings)

        call = session.get(AICall, processed.ai_call_id)
        assert call.status == "SUCCEEDED"
        assert call.latency_ms is not None and call.latency_ms >= 0
        audit = session.scalar(select(AuditEvent).where(AuditEvent.event_type == "speech.asr.succeeded"))
        assert audit is not None and audit.payload["raw_preserved"] is True


def test_asr_job_empty_transcript_schedules_retry_then_fails() -> None:
    engine = _db_engine()
    with Session(engine) as session:
        answer = Answer(attempt_item_id=uuid.uuid4(), answer_type="MAIN")
        session.add(answer)
        session.flush()
        storage = MemoryStorage()
        storage.store("answers/key.wav", _wav_bytes())
        job = enqueue_asr_job(
            session,
            answer_id=answer.id,
            storage_key="answers/key.wav",
            filename="key.wav",
            mime_type="audio/wav",
            business_key=f"asr-empty-{answer.id}",
            max_retries=1,
        )
        session.commit()

        _run(process_asr_job(session, job, FakeSpeechProvider(""), storage))
        assert job.state == TaskJobState.RETRY_SCHEDULED.value
        assert job.run_after is not None
        assert job.last_error is not None
        session.commit()

        _run(process_asr_job(session, job, FakeSpeechProvider(""), storage))
        assert job.state == TaskJobState.FAILED.value
        assert job.completed_at is not None
        assert not session.scalars(select(ASRTranscript)).all()


def test_tts_job_pipeline_stores_media_asset_and_audits() -> None:
    engine = _db_engine()
    with Session(engine) as session:
        job = enqueue_tts_job(
            session,
            business_key="tts-demo",
            text="请说明放行流程。",
            purpose=AudioPurpose.QUESTION_TTS,
            max_retries=1,
        )
        session.commit()

        storage = MemoryStorage()
        processed = _run(process_tts_job(session, job, FakeSpeechProvider(), storage))
        session.commit()

        assert processed.state == TaskJobState.SUCCEEDED.value
        asset = session.scalar(select(MediaAsset))
        assert asset is not None
        assert asset.purpose == AudioPurpose.QUESTION_TTS.value
        assert asset.mime_type == "audio/wav"
        assert asset.duration_ms == 1000
        assert asset.sha256 == hashlib.sha256(_wav_bytes()).hexdigest()
        assert storage.exists(asset.storage_key)
        call = session.get(AICall, processed.ai_call_id)
        assert call.status == "SUCCEEDED"
        assert call.latency_ms is not None
        assert session.scalar(select(AuditEvent).where(AuditEvent.event_type == "speech.tts.succeeded")) is not None


def test_tts_job_failure_degrades_to_stored_text() -> None:
    engine = _db_engine()
    with Session(engine) as session:
        job = enqueue_tts_job(
            session,
            business_key="tts-fail",
            text="题干文本降级",
            max_retries=1,
        )
        session.commit()
        permanent = ProviderFailure("auth rejected", kind=ProviderFailureKind.PERMANENT, code="HTTP_ERROR")
        processed = _run(process_tts_job(session, job, AlwaysFailSpeechProvider(permanent), MemoryStorage()))
        assert processed.state == TaskJobState.FAILED.value
        assert tts_fallback_text(processed) == "题干文本降级"


def test_ai_call_records_redact_credentials_and_latency() -> None:
    engine = _db_engine()
    with Session(engine) as session:
        call = create_ai_call(
            session,
            task_type="ASR",
            provider="MIMO",
            model="mimo-v2.5-asr",
            raw_response={"authorization": "Bearer sekret", "nested": {"api_key": "x"}, "text": "ok"},
            status="SUCCEEDED",
            latency_ms=42,
        )
        session.commit()
        session.refresh(call)
        assert call.raw_response == {
            "authorization": "[REDACTED]",
            "nested": {"api_key": "[REDACTED]"},
            "text": "ok",
        }
        assert call.latency_ms == 42


def test_media_access_url_signing_roundtrip() -> None:
    settings = Settings(_env_file=None, media_url_secret="test-secret")
    expires = int(time.time()) + 3600
    url = sign_media_url("answers/a/1.wav", expires, settings)
    assert "/api/v1/media/answers/a/1.wav?expires=" in url
    assert "sig=" in url
    assert verify_media_signature("answers/a/1.wav", expires, url.split("sig=")[1], settings) is True
    assert verify_media_signature("answers/a/1.wav", expires, "deadbeef", settings) is False
    assert verify_media_signature("answers/a/other.wav", expires, url.split("sig=")[1], settings) is False


@pytest.fixture
def api_client(tmp_path) -> TestClient:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    storage = LocalStorageAdapter(str(tmp_path))

    with testing_session() as session:
        content = _wav_bytes()
        storage.store("answers/demo.wav", content)
        session.add(
            MediaAsset(
                storage_key="answers/demo.wav",
                purpose=AudioPurpose.CANDIDATE_ANSWER.value,
                mime_type="audio/wav",
                size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                retention={},
            )
        )
        session.commit()

    def override_get_db():
        with testing_session() as session:
            yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_media_storage] = lambda: storage
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_media_route_serves_only_signed_short_lived_urls(api_client: TestClient, tmp_path) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    expires = int(time.time()) + 3600
    url = sign_media_url("answers/demo.wav", expires, settings)
    response = api_client.get(url)
    assert response.status_code == 200
    assert response.content == _wav_bytes()
    assert response.headers["content-type"] == "audio/wav"

    tampered = url.replace("sig=", "sig=0")
    assert api_client.get(tampered).status_code == 403

    expired = sign_media_url("answers/demo.wav", int(time.time()) - 10, settings)
    assert api_client.get(expired).status_code == 403

    unknown = sign_media_url("answers/nope.wav", int(time.time()) + 3600, settings)
    assert api_client.get(unknown).status_code == 404


def test_speech_job_dispatcher_rejects_unknown_job_type() -> None:
    engine = _db_engine()
    with Session(engine) as session:
        job = TaskJob(job_type="UNKNOWN", business_key="x", payload={})
        session.add(job)
        session.commit()
        with pytest.raises(ValueError):
            _run(process_speech_job(session, job, FakeSpeechProvider(), MemoryStorage()))
