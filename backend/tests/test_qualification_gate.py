"""Sprint 1B Formal Speech Qualification Gate regression coverage.

Locks: normalizer ruleset version persistence + independent traceability of ruleset vs
vocabulary version, qualification metric calculation, empty/false-correction accounting,
deterministic manifests, artifact redaction, and the offline harness artifact writer.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from app.core.config import Settings
from app.core.security import redact
from app.db.base import Base
from app.models.domain import ASRNormalization, ASRTranscript, VocabularyTerm, VocabularyVersion
from app.normalization.normalizer import NORMALIZER_RULESET_VERSION, normalize
from app.normalization.vocabulary import VocabularySnapshot
from app.qualification.metrics import (
    build_manifest,
    detect_false_corrections,
    p50,
    p95,
    summarize_asr,
    summarize_tts,
    term_accuracy,
    text_similarity,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def _run(coro) -> object:
    return asyncio.run(coro)


def test_normalizer_reports_ruleset_version() -> None:
    result = normalize("B七三七NG 维修放心", VocabularySnapshot(version="builtin"))
    assert result.ruleset_version == NORMALIZER_RULESET_VERSION
    assert result.vocabulary_version == "builtin"


def _asr_pipeline(engine) -> None:
    from app.ai.providers.speech.fake import FakeSpeechProvider
    from app.models.domain import Answer
    from app.services.speech_jobs import enqueue_asr_job, process_asr_job

    class MemoryStorage:
        def __init__(self) -> None:
            self.contents: dict[str, bytes] = {}

        def store(self, key: str, content: bytes):
            from app.audio.storage import StorageRef

            self.contents[key] = content
            return StorageRef(key=key)

        def read(self, key: str) -> bytes:
            return self.contents[key]

        def exists(self, key: str) -> bool:
            return key in self.contents

    with Session(engine) as session:
        answer = Answer(attempt_item_id=uuid.uuid4(), answer_type="MAIN")
        session.add(answer)
        session.flush()
        storage = MemoryStorage()
        storage.store("answers/key.wav", b"\x00" * 4000)
        job = enqueue_asr_job(
            session,
            answer_id=answer.id,
            storage_key="answers/key.wav",
            filename="key.wav",
            mime_type="audio/wav",
            business_key=f"qual-{answer.id}",
            max_retries=1,
        )
        session.commit()
        _run(process_asr_job(session, job, FakeSpeechProvider("B七三七NG 维修放心"), storage))
        session.commit()

        transcript_id = session.scalars(select(ASRTranscript)).one().id
        norm = session.scalar(
            select(ASRNormalization).where(ASRNormalization.transcript_id == transcript_id)
        )
        assert norm is not None
        assert norm.normalizer_ruleset_version == NORMALIZER_RULESET_VERSION
        assert norm.vocabulary_version_id is None  # ruleset and vocab are independent
        assert norm.normalized_text == "B737NG 维修放行"


def test_asr_pipeline_persists_ruleset_version() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    _asr_pipeline(engine)


def test_historical_normalization_keeps_its_ruleset_version() -> None:
    """Normalization records are immutable: an old ruleset version is never rewritten."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        historical = ASRNormalization(
            transcript_id=uuid.uuid4(),
            normalizer_ruleset_version="builtin-v0",
            normalized_text="B737NG 维修放行",
        )
        session.add(historical)
        session.commit()
        loaded = session.get(ASRNormalization, historical.id)
        assert loaded.normalizer_ruleset_version == "builtin-v0"
        # Current code constant may move on, but history stays pinned to its own version.


def test_vocabulary_and_ruleset_versions_independently_traceable() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        vocab = VocabularyVersion(
            vocabulary_id=uuid.uuid4(), version=3, status="PUBLISHED", published_by="qual"
        )
        session.add(vocab)
        session.flush()
        term = VocabularyTerm(
            vocabulary_version_id=vocab.id, canonical_text="B737NG", aliases=["B七三七NG"]
        )
        session.add(term)
        session.flush()
        norm = ASRNormalization(
            transcript_id=uuid.uuid4(),
            vocabulary_version_id=vocab.id,
            normalizer_ruleset_version=NORMALIZER_RULESET_VERSION,
            normalized_text="B737NG",
        )
        session.add(norm)
        session.commit()
        loaded = session.get(ASRNormalization, norm.id)
        assert loaded.vocabulary_version_id == vocab.id
        assert loaded.normalizer_ruleset_version == NORMALIZER_RULESET_VERSION


def test_qualification_metric_calculation() -> None:
    assert text_similarity("B737NG", "B737NG") == 1.0
    assert text_similarity("B737NG", "") == 0.0
    assert term_accuracy("根据 MEL 放行", ["MEL", "放行"]) == 1.0
    assert term_accuracy("根据 M E L 放行", ["MEL"]) == 0.0
    assert p50([10, 20, 30, 40]) == 25.0
    assert p95([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]) > 18

    asr_results = [
        {"status": "SUCCESS", "latency_ms": 100, "raw_similarity": 0.9, "norm_similarity": 0.95,
         "raw_term_accuracy": 0.5, "norm_term_accuracy": 1.0, "false_corrections": [], "warnings": [], "retries": 0},
        {"status": "SUCCESS", "latency_ms": 200, "raw_similarity": 0.8, "norm_similarity": 0.9,
         "raw_term_accuracy": 0.5, "norm_term_accuracy": 1.0, "false_corrections": [{"x": 1}], "warnings": ["low"], "retries": 1},
        {"status": "EMPTY", "reason": "empty", "retries": 2},
    ]
    metrics = summarize_asr(asr_results)
    assert metrics["request_success_rate"] == pytest.approx(round(2 / 3, 4), abs=1e-3)
    assert metrics["empty_transcript_rate"] == pytest.approx(round(1 / 3, 4), abs=1e-3)
    assert metrics["false_correction_count"] == 1
    assert metrics["normalization_improvement"] == 0.5
    assert metrics["latency_ms_p50"] == 150.0
    assert metrics["review_required_rate"] == pytest.approx(round(2 / 3, 4), abs=1e-3)

    tts_metrics = summarize_tts(
        [
            {"status": "SUCCESS", "tts_latency_ms": 300, "round_trip_term_accuracy": 1.0, "retries": 0},
            {"status": "EMPTY_AUDIO", "reason": "empty audio", "retries": 1},
        ]
    )
    assert tts_metrics["empty_audio_rate"] == 0.5
    assert tts_metrics["latency_ms_p50"] == 300.0


def test_empty_transcript_counted_as_not_success() -> None:
    metrics = summarize_asr(
        [
            {"status": "SUCCESS", "latency_ms": 50, "raw_term_accuracy": 1.0, "norm_term_accuracy": 1.0,
             "raw_similarity": 1.0, "norm_similarity": 1.0, "false_corrections": [], "warnings": [], "retries": 0},
            {"status": "EMPTY", "reason": "empty", "retries": 2},
        ]
    )
    assert metrics["success_count"] == 1
    assert metrics["empty_count"] == 1
    assert metrics["request_success_rate"] == pytest.approx(0.5, abs=1e-3)
    assert metrics["non_empty_transcript_rate"] == 0.5


def test_false_normalization_detection() -> None:
    class Mapping:
        def __init__(self, raw, norm, rule, confidence=1.0):
            self.raw_fragment = raw
            self.normalized_fragment = norm
            self.normalization_rule = rule
            self.confidence = confidence

    # Correct alias -> canonical: normalized fragment present in gold -> not flagged.
    good = Mapping("维修放心", "维修放行", "LAYER_2_CONTEXT_ALIAS")
    # Dangerous: rewrote a plain token into an abbreviation the gold never contained.
    bad = Mapping("sb", "SB", "VOCABULARY_ALIAS", 0.9)
    flagged = detect_false_corrections("完成维修放行流程", [good, bad])
    assert len(flagged) == 1
    assert flagged[0]["normalized_fragment"] == "SB"


def test_manifest_deterministic() -> None:
    cases = [{"case_id": "asr-01", "category": "A", "text": "x"}]
    first = build_manifest(
        run_id="run-1",
        dataset_version="v1",
        normalizer_ruleset_version="builtin-v1",
        vocabulary_version="builtin",
        asr_cases=cases,
        tts_cases=[],
    )
    second = build_manifest(
        run_id="run-1",
        dataset_version="v1",
        normalizer_ruleset_version="builtin-v1",
        vocabulary_version="builtin",
        asr_cases=cases,
        tts_cases=[],
    )
    assert first == second
    json.loads(first)  # valid JSON


def test_secrets_never_enter_qualification_artifact() -> None:
    payload = {"api_key": "sk-secret", "authorization": "Bearer x", "nested": {"token": "t"}}
    cleaned = redact(payload)
    assert cleaned == {
        "api_key": "[REDACTED]",
        "authorization": "[REDACTED]",
        "nested": {"token": "[REDACTED]"},
    }
    serialized = json.dumps(cleaned)
    assert "sk-secret" not in serialized and "Bearer x" not in serialized


def test_offline_harness_writes_all_artifacts(tmp_path) -> None:
    from scripts.speech_qualification.run import run_qualification

    settings = Settings(_env_file=None)
    output = _run(
        run_qualification(
            run_id="offline-test",
            output_dir=tmp_path / "artifacts",
            settings=settings,
            provider_kind="fake",
            max_retries=0,
        )
    )
    expected = {
        "manifest.json",
        "results.json",
        "metrics.json",
        "failures.json",
        "normalization-errors.json",
        "report.md",
    }
    assert {p.name for p in output.iterdir()} == expected
    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert "asr" in metrics and "tts" in metrics
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == "offline-test"
    results = json.loads((output / "results.json").read_text(encoding="utf-8"))
    statuses = {r["status"] for r in results["asr_results"]}
    # Human-speech cases are not evaluated without an audio dir.
    assert "SKIPPED" in statuses
