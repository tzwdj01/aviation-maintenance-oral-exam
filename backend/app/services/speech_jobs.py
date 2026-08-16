"""Durable speech TaskJob orchestration (Sprint 1B).

The business layer only talks to the `SpeechProvider` protocol; provider-specific payloads
stay inside ``app/ai/providers/speech/``. Raw ASR is always preserved, adoption is explicit
and single, and TTS failures degrade to the stored stem text.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.providers.base import (
    AudioReference,
    ProviderFailure,
    ProviderFailureKind,
    SpeechProvider,
)
from app.audio.storage import StorageAdapter
from app.core.config import get_settings
from app.core.enums import AudioPurpose, TaskJobState, TaskJobType
from app.models.domain import (
    ASRNormalization,
    ASRTranscript,
    MediaAsset,
    NormalizationMapping,
    TaskJob,
    VocabularyTerm,
    VocabularyVersion,
)
from app.normalization.normalizer import normalize
from app.normalization.vocabulary import VocabularyEntry, VocabularySnapshot
from app.repositories.core import adopt_transcript
from app.services.ai_calls import create_ai_call
from app.services.audit import record_audit_event
from app.services.jobs import backoff_seconds
from app.speech.render import render_for_tts


def enqueue_asr_job(
    session: Session,
    *,
    answer_id: uuid.UUID,
    storage_key: str,
    filename: str,
    mime_type: str,
    business_key: str,
    language: str | None = None,
    model: str | None = None,
    max_retries: int | None = None,
) -> TaskJob:
    settings = get_settings()
    job = TaskJob(
        job_type=TaskJobType.ASR.value,
        state=TaskJobState.PENDING.value,
        business_key=business_key,
        answer_id=answer_id,
        payload={
            "answer_id": str(answer_id),
            "storage_key": storage_key,
            "filename": filename,
            "mime_type": mime_type,
            "language": language or settings.mimo_asr_language,
            "model": model or settings.mimo_asr_model,
            "provider": "MIMO",
            "max_retries": max_retries if max_retries is not None else settings.ai_max_retries,
        },
    )
    session.add(job)
    session.flush()
    return job


def enqueue_tts_job(
    session: Session,
    *,
    business_key: str,
    text: str,
    voice: str | None = None,
    purpose: AudioPurpose = AudioPurpose.QUESTION_TTS,
    attempt_item_id: uuid.UUID | None = None,
    model: str | None = None,
    max_retries: int | None = None,
) -> TaskJob:
    settings = get_settings()
    render_profile_version = settings.speech_render_profile_version
    rendered_text = render_for_tts(text)
    job = TaskJob(
        job_type=TaskJobType.TTS.value,
        state=TaskJobState.PENDING.value,
        business_key=business_key,
        attempt_item_id=attempt_item_id,
        payload={
            "text": rendered_text,
            "canonical_text": text,
            "render_profile_version": render_profile_version,
            "voice": voice or settings.mimo_tts_voice,
            "purpose": purpose.value,
            "model": model or settings.mimo_tts_model,
            "provider": "MIMO",
            "max_retries": max_retries if max_retries is not None else settings.ai_max_retries,
            "fallback_text": text,
        },
    )
    session.add(job)
    session.flush()
    return job


def tts_fallback_text(job: TaskJob) -> str | None:
    """Degradation path: when TTS terminal-fails, the presentation layer must use the text."""
    if job.state == TaskJobState.FAILED.value and job.payload.get("fallback_text"):
        return job.payload["fallback_text"]
    return None


def load_vocabulary_snapshot(session: Session) -> tuple[VocabularySnapshot, uuid.UUID | None]:
    """Load the latest published vocabulary (or an empty builtin snapshot) for normalization."""
    version = session.scalar(
        select(VocabularyVersion)
        .where(VocabularyVersion.status == "PUBLISHED")
        .order_by(VocabularyVersion.published_at.desc(), VocabularyVersion.created_at.desc())
        .limit(1)
    )
    if version is None:
        return VocabularySnapshot(version="builtin"), None
    terms = tuple(
        VocabularyEntry(
            canonical=term.canonical_text,
            aliases=tuple(term.aliases or ()),
            context_hints=tuple(term.context_hints or ()),
        )
        for term in session.scalars(
            select(VocabularyTerm).where(VocabularyTerm.vocabulary_version_id == version.id)
        )
    )
    return VocabularySnapshot(version=str(version.version), terms=terms), version.id


def _audio_from_payload(storage: StorageAdapter, payload: dict[str, Any]) -> AudioReference:
    return AudioReference(
        content=storage.read(payload["storage_key"]),
        filename=payload.get("filename", "audio.bin"),
        mime_type=payload["mime_type"],
    )


async def process_asr_job(
    session: Session,
    job: TaskJob,
    provider: SpeechProvider,
    storage: StorageAdapter,
) -> TaskJob:
    if job.state == TaskJobState.SUCCEEDED.value:
        return job
    job.state = TaskJobState.RUNNING.value
    job.attempts += 1
    payload = dict(job.payload)
    answer_id = uuid.UUID(payload["answer_id"]) if payload.get("answer_id") else None
    started = datetime.now(UTC)
    try:
        result = await provider.transcribe(_audio_from_payload(storage, payload))
    except ProviderFailure as exc:
        return _fail_asr_job(session, job, payload, started, exc)

    latency_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    raw_text = result.text
    if not raw_text or not raw_text.strip():
        empty = ProviderFailure(
            "ASR returned an empty transcript",
            kind=ProviderFailureKind.TEMPORARY,
            code="EMPTY_TRANSCRIPT",
            request_id=result.request_id,
        )
        return _fail_asr_job(session, job, payload, started, empty)

    transcript = ASRTranscript(
        answer_id=answer_id,
        provider=provider.provider_name,
        model=result.model,
        raw_text=raw_text,
        raw_response=result.raw_response,
        language=payload.get("language"),
    )
    session.add(transcript)
    session.flush()

    vocab, vocab_version_id = load_vocabulary_snapshot(session)
    normalized = normalize(raw_text, vocab)
    asr_norm = ASRNormalization(
        transcript_id=transcript.id,
        vocabulary_version_id=vocab_version_id,
        normalizer_ruleset_version=normalized.ruleset_version,
        normalized_text=normalized.normalized_text,
        warnings=list(normalized.warnings),
    )
    session.add(asr_norm)
    session.flush()
    for mapping in normalized.mappings:
        session.add(
            NormalizationMapping(
                normalization_id=asr_norm.id,
                raw_fragment=mapping.raw_fragment,
                normalized_fragment=mapping.normalized_fragment,
                start_char=mapping.start_char,
                end_char=mapping.end_char,
                confidence=Decimal(str(mapping.confidence)),
                normalization_rule=mapping.normalization_rule,
            )
        )
    adopt_transcript(session, transcript, actor_id="system:asr-job")

    call = create_ai_call(
        session,
        task_type=TaskJobType.ASR.value,
        provider=provider.provider_name,
        model=result.model,
        request_id=result.request_id,
        input_summary={"answer_id": str(answer_id), "language": payload.get("language")},
        raw_response=result.raw_response,
        status="SUCCEEDED",
        retry_count=job.attempts,
        latency_ms=latency_ms,
    )
    job.state = TaskJobState.SUCCEEDED.value
    job.completed_at = datetime.now(UTC)
    job.last_error = None
    job.ai_call_id = call.id
    record_audit_event(
        session,
        "speech.asr.succeeded",
        "task_job",
        str(job.id),
        {
            "transcript_id": str(transcript.id),
            "normalization_id": str(asr_norm.id),
            "raw_preserved": True,
            "is_adopted": True,
            "latency_ms": latency_ms,
        },
    )
    return job


def _fail_asr_job(
    session: Session,
    job: TaskJob,
    payload: dict[str, Any],
    started: datetime,
    exc: ProviderFailure,
) -> TaskJob:
    latency_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    max_retries = int(payload.get("max_retries") or get_settings().ai_max_retries)
    retryable = exc.kind == ProviderFailureKind.TEMPORARY and job.attempts <= max_retries
    create_ai_call(
        session,
        task_type=TaskJobType.ASR.value,
        provider=str(payload.get("provider") or "MIMO"),
        model=str(payload.get("model") or ""),
        request_id=exc.request_id,
        input_summary={"answer_id": payload.get("answer_id"), "language": payload.get("language")},
        status="FAILED",
        error=str(exc),
        retry_count=job.attempts,
        latency_ms=latency_ms,
    )
    job.last_error = str(exc)
    if retryable:
        job.state = TaskJobState.RETRY_SCHEDULED.value
        job.run_after = datetime.now(UTC) + timedelta(seconds=backoff_seconds(job.attempts))
        record_audit_event(
            session,
            "speech.asr.retry_scheduled",
            "task_job",
            str(job.id),
            {"error_code": exc.code, "attempt": job.attempts},
        )
    else:
        job.state = TaskJobState.FAILED.value
        job.completed_at = datetime.now(UTC)
        record_audit_event(
            session,
            "speech.asr.failed",
            "task_job",
            str(job.id),
            {
                "error_code": exc.code,
                "permanent": exc.kind == ProviderFailureKind.PERMANENT,
                "needs_attention": True,
                "re_recording_supported": True,
            },
        )
    return job


async def process_tts_job(
    session: Session,
    job: TaskJob,
    provider: SpeechProvider,
    storage: StorageAdapter,
) -> TaskJob:
    if job.state == TaskJobState.SUCCEEDED.value:
        return job
    job.state = TaskJobState.RUNNING.value
    job.attempts += 1
    payload = dict(job.payload)
    started = datetime.now(UTC)
    try:
        result = await provider.synthesize(payload["text"], voice=payload.get("voice"))
    except ProviderFailure as exc:
        return _fail_tts_job(session, job, payload, started, exc)

    latency_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    if not result.content:
        empty = ProviderFailure(
            "TTS returned empty audio",
            kind=ProviderFailureKind.TEMPORARY,
            code="EMPTY_AUDIO",
            request_id=result.request_id,
        )
        return _fail_tts_job(session, job, payload, started, empty)

    from app.audio.validation import AudioValidationError, validate_audio

    settings = get_settings()
    try:
        metadata = validate_audio(
            AudioReference(content=result.content, filename="tts.wav", mime_type=result.mime_type),
            max_size_bytes=settings.media_max_size_bytes,
            allowed_mime_types=settings.media_allowed_mime_types,
            max_duration_seconds=settings.media_max_duration_seconds,
        )
    except AudioValidationError as exc:
        invalid = ProviderFailure(
            f"TTS produced invalid audio: {exc}",
            kind=ProviderFailureKind.TEMPORARY,
            code="INVALID_AUDIO",
            request_id=result.request_id,
        )
        return _fail_tts_job(session, job, payload, started, invalid)

    extension = "mp3" if metadata.mime_type == "audio/mpeg" else "wav"
    storage_key = f"{payload.get('purpose', AudioPurpose.QUESTION_TTS.value).lower()}/{job.id}.{extension}"
    storage.store(storage_key, result.content)
    asset = MediaAsset(
        storage_key=storage_key,
        purpose=payload.get("purpose", AudioPurpose.QUESTION_TTS.value),
        mime_type=metadata.mime_type,
        codec=metadata.codec,
        sample_rate=metadata.sample_rate,
        channels=metadata.channels,
        duration_ms=metadata.duration_ms,
        size_bytes=metadata.size_bytes,
        sha256=metadata.sha256,
        retention={},
        attempt_item_id=job.attempt_item_id,
    )
    session.add(asset)
    session.flush()

    call = create_ai_call(
        session,
        task_type=TaskJobType.TTS.value,
        provider=provider.provider_name,
        model=result.model,
        request_id=result.request_id,
        input_summary={
            "text_preview": payload["text"][:120],
            "canonical_preview": (payload.get("canonical_text") or payload["text"])[:120],
            "render_profile_version": payload.get("render_profile_version"),
            "voice": payload.get("voice"),
        },
        raw_response=result.raw_response,
        status="SUCCEEDED",
        retry_count=job.attempts,
        latency_ms=latency_ms,
    )
    job.state = TaskJobState.SUCCEEDED.value
    job.completed_at = datetime.now(UTC)
    job.last_error = None
    job.ai_call_id = call.id
    record_audit_event(
        session,
        "speech.tts.succeeded",
        "task_job",
        str(job.id),
        {"media_asset_id": str(asset.id), "latency_ms": latency_ms},
    )
    return job


def _fail_tts_job(
    session: Session,
    job: TaskJob,
    payload: dict[str, Any],
    started: datetime,
    exc: ProviderFailure,
) -> TaskJob:
    latency_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    max_retries = int(payload.get("max_retries") or get_settings().ai_max_retries)
    retryable = exc.kind == ProviderFailureKind.TEMPORARY and job.attempts <= max_retries
    create_ai_call(
        session,
        task_type=TaskJobType.TTS.value,
        provider=str(payload.get("provider") or "MIMO"),
        model=str(payload.get("model") or ""),
        request_id=exc.request_id,
        input_summary={"text_preview": payload.get("text", "")[:120]},
        status="FAILED",
        error=str(exc),
        retry_count=job.attempts,
        latency_ms=latency_ms,
    )
    job.last_error = str(exc)
    if retryable:
        job.state = TaskJobState.RETRY_SCHEDULED.value
        job.run_after = datetime.now(UTC) + timedelta(seconds=backoff_seconds(job.attempts))
        record_audit_event(
            session,
            "speech.tts.retry_scheduled",
            "task_job",
            str(job.id),
            {"error_code": exc.code, "attempt": job.attempts},
        )
    else:
        job.state = TaskJobState.FAILED.value
        job.completed_at = datetime.now(UTC)
        record_audit_event(
            session,
            "speech.tts.failed",
            "task_job",
            str(job.id),
            {"error_code": exc.code, "permanent": exc.kind == ProviderFailureKind.PERMANENT},
        )
    return job


async def process_speech_job(
    session: Session,
    job: TaskJob,
    provider: SpeechProvider,
    storage: StorageAdapter,
) -> TaskJob:
    job_type = TaskJobType(job.job_type)
    if job_type is TaskJobType.ASR:
        return await process_asr_job(session, job, provider, storage)
    if job_type is TaskJobType.TTS:
        return await process_tts_job(session, job, provider, storage)
    raise ValueError(f"Unsupported speech job type: {job.job_type}")
