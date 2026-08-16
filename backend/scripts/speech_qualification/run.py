"""Formal Speech Qualification runner for the Sprint 1B Speech Gate.

Usage:
    python -m scripts.speech_qualification.run \
        [--run-id 2026-08-16-s1b-qual-v1] \
        [--audio-dir <dir-with-human-cases>] \
        [--asr-only | --tts-only] [--max-cases N] [--provider mimo|fake]

Credentials are read from the environment via ``app.core.config.Settings`` and are never
printed or persisted. Human-speech cases are only evaluated when matching audio exists in
``--audio-dir``; otherwise they are recorded as ``SKIPPED`` (not_evaluated).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.ai.providers.base import (
    AudioReference,
    ProviderFailure,
    ProviderFailureKind,
    SpeechProvider,
)
from app.ai.providers.speech.fake import FakeSpeechProvider
from app.ai.providers.speech.mimo_asr import MiMoASRProvider
from app.ai.providers.speech.mimo_tts import MiMoTTSProvider
from app.audio.validation import AudioValidationError, validate_audio
from app.core.config import Settings, get_settings
from app.core.security import redact
from app.normalization.normalizer import NORMALIZER_RULESET_VERSION, normalize
from app.normalization.vocabulary import VocabularySnapshot
from app.qualification.metrics import (
    build_manifest,
    detect_false_corrections,
    summarize_asr,
    summarize_tts,
    term_accuracy,
    text_similarity,
)
from app.services.jobs import backoff_seconds

from scripts.speech_qualification.dataset import (
    ASR_CASES,
    DATASET_VERSION,
    TTS_CASES,
    VOCABULARY_VERSION,
)


def _audio_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _mime_for(path: Path) -> str:
    return "audio/mpeg" if path.suffix.lower() == ".mp3" else "audio/wav"


def _build_providers(settings: Settings, provider_kind: str) -> tuple[SpeechProvider, SpeechProvider]:
    if provider_kind == "fake":
        return FakeSpeechProvider(), FakeSpeechProvider()
    key = settings.mimo_api_key.get_secret_value() if settings.mimo_api_key else None
    asr = MiMoASRProvider(
        settings.mimo_base_url,
        key,
        settings.mimo_asr_model,
        language=settings.mimo_asr_language,
        connect_timeout_seconds=settings.ai_connect_timeout_seconds,
        request_timeout_seconds=settings.ai_request_timeout_seconds,
    )
    tts = MiMoTTSProvider(
        settings.mimo_base_url,
        key,
        settings.mimo_tts_model,
        voice=settings.mimo_tts_voice,
        connect_timeout_seconds=settings.ai_connect_timeout_seconds,
        request_timeout_seconds=settings.ai_request_timeout_seconds,
    )
    return asr, tts


async def _synthesize_with_retry(
    provider: SpeechProvider, text: str, voice: str | None, max_retries: int
) -> tuple[bool, Any, int, int]:
    """Return (ok, SynthesizedAudio|ProviderFailure, latency_ms, retries)."""
    retries = 0
    while True:
        started = time.monotonic()
        try:
            result = await provider.synthesize(text, voice=voice)
            return True, result, int((time.monotonic() - started) * 1000), retries
        except ProviderFailure as exc:
            latency = int((time.monotonic() - started) * 1000)
            if exc.kind == ProviderFailureKind.TEMPORARY and retries < max_retries:
                retries += 1
                await asyncio.sleep(backoff_seconds(retries + 1))
                continue
            return False, exc, latency, retries


async def _transcribe_with_retry(
    provider: SpeechProvider, audio: AudioReference, max_retries: int
) -> tuple[bool, Any, int, int]:
    """Return (ok, TranscriptResult|ProviderFailure, latency_ms, retries)."""
    retries = 0
    while True:
        started = time.monotonic()
        try:
            result = await provider.transcribe(audio)
            return True, result, int((time.monotonic() - started) * 1000), retries
        except ProviderFailure as exc:
            latency = int((time.monotonic() - started) * 1000)
            if exc.kind == ProviderFailureKind.TEMPORARY and retries < max_retries:
                retries += 1
                await asyncio.sleep(backoff_seconds(retries + 1))
                continue
            return False, exc, latency, retries


async def _resolve_audio(
    case: dict[str, Any],
    *,
    audio_dir: Path | None,
    tts_provider: SpeechProvider,
    settings: Settings,
    max_retries: int,
) -> tuple[AudioReference | None, dict[str, Any], str | None]:
    """Resolve case audio: human audio from disk or TTS-synthesized reference audio."""
    if case.get("source") == "human":
        if audio_dir is None:
            return None, {}, "human audio dir not provided"
        candidates = [p for p in audio_dir.glob(f"{case['case_id']}.*") if p.suffix.lower() in {".wav", ".mp3"}]
        if not candidates:
            return None, {}, f"human audio missing for {case['case_id']}"
        path = min(candidates)
        content = path.read_bytes()
        reference = AudioReference(content=content, filename=path.name, mime_type=_mime_for(path))
        return reference, {"audio_source": "human", "audio_file": path.name}, None

    ok, result, latency_ms, retries = await _synthesize_with_retry(
        tts_provider, case["text"], None, max_retries
    )
    if not ok or not result.content:
        return None, {"tts_latency_ms": latency_ms, "tts_retries": retries}, (
            f"reference TTS synthesis failed: {result}"
        )
    reference = AudioReference(
        content=result.content, filename="reference.wav", mime_type=result.mime_type
    )
    return reference, {"audio_source": "tts_synthetic", "tts_latency_ms": latency_ms, "tts_retries": retries}, None


def _normalize_result(text: str) -> dict[str, Any]:
    normalized = normalize(text, VocabularySnapshot(version=VOCABULARY_VERSION))
    return {
        "normalized_text": normalized.normalized_text,
        "mappings": [
            {
                "raw_fragment": m.raw_fragment,
                "normalized_fragment": m.normalized_fragment,
                "start_char": m.start_char,
                "end_char": m.end_char,
                "confidence": m.confidence,
                "normalization_rule": m.normalization_rule,
            }
            for m in normalized.mappings
        ],
        "warnings": list(normalized.warnings),
        "normalizer_ruleset_version": normalized.ruleset_version,
        "vocabulary_version": normalized.vocabulary_version,
    }


async def run_asr_case(
    case: dict[str, Any],
    *,
    asr_provider: SpeechProvider,
    tts_provider: SpeechProvider,
    settings: Settings,
    audio_dir: Path | None,
    max_retries: int,
) -> dict[str, Any]:
    base = {
        "case_id": case["case_id"],
        "category": case["category"],
        "source": case.get("source", "tts"),
        "condition": case.get("condition", "normal"),
        "gold_text": case["text"],
        "expected_terms": case["expected_terms"],
    }
    audio, audio_meta, skip_reason = await _resolve_audio(
        case, audio_dir=audio_dir, tts_provider=tts_provider, settings=settings, max_retries=max_retries
    )
    if audio is None:
        return {**base, "status": "SKIPPED", "reason": skip_reason, "audio_metadata": audio_meta}

    try:
        metadata = validate_audio(
            audio,
            max_size_bytes=settings.media_max_size_bytes,
            allowed_mime_types=settings.media_allowed_mime_types,
            max_duration_seconds=settings.media_max_duration_seconds,
        )
    except AudioValidationError as exc:
        return {
            **base,
            "status": "FAILED",
            "reason": f"invalid audio before ASR: {exc}",
            "audio_metadata": audio_meta,
        }
    audio_meta.update(
        {
            "audio_hash": _audio_hash(audio.content),
            "mime_type": metadata.mime_type,
            "size_bytes": metadata.size_bytes,
            "duration_ms": metadata.duration_ms,
        }
    )

    ok, result, latency_ms, retries = await _transcribe_with_retry(asr_provider, audio, max_retries)
    if not ok:
        empty = isinstance(result, ProviderFailure) and result.code == "EMPTY_TRANSCRIPT"
        return {
            **base,
            "status": "EMPTY" if empty else "FAILED",
            "reason": str(result),
            "error_code": getattr(result, "code", None),
            "latency_ms": latency_ms,
            "retries": retries,
            "audio_metadata": audio_meta,
            "raw_transcript": None,
        }

    raw_text = result.text or ""
    if not raw_text.strip():
        return {
            **base,
            "status": "EMPTY",
            "reason": "provider returned empty transcript without error",
            "latency_ms": latency_ms,
            "retries": retries,
            "audio_metadata": audio_meta,
            "raw_transcript": raw_text,
        }
    norm = _normalize_result(raw_text)
    false_corrections = detect_false_corrections(case["text"], [m for m in norm["mappings"]])
    return {
        **base,
        "status": "SUCCESS",
        "latency_ms": latency_ms,
        "retries": retries,
        "audio_metadata": audio_meta,
        "raw_transcript": raw_text,
        "raw_similarity": text_similarity(case["text"], raw_text),
        "raw_term_accuracy": term_accuracy(raw_text, case["expected_terms"]),
        **norm,
        "norm_similarity": text_similarity(case["text"], norm["normalized_text"]),
        "norm_term_accuracy": term_accuracy(norm["normalized_text"], case["expected_terms"]),
        "false_corrections": false_corrections,
    }


async def run_tts_case(
    case: dict[str, Any],
    *,
    tts_provider: SpeechProvider,
    asr_provider: SpeechProvider,
    settings: Settings,
    max_retries: int,
) -> dict[str, Any]:
    base = {
        "case_id": case["case_id"],
        "category": case["category"],
        "gold_text": case["text"],
        "expected_terms": case["expected_terms"],
    }
    ok, result, tts_latency_ms, retries = await _synthesize_with_retry(
        tts_provider, case["text"], None, max_retries
    )
    if not ok:
        return {
            **base,
            "status": "FAILED",
            "reason": str(result),
            "error_code": getattr(result, "code", None),
            "tts_latency_ms": tts_latency_ms,
            "retries": retries,
        }
    if not result.content:
        return {
            **base,
            "status": "EMPTY_AUDIO",
            "reason": "provider returned empty audio",
            "tts_latency_ms": tts_latency_ms,
            "retries": retries,
        }
    try:
        metadata = validate_audio(
            AudioReference(content=result.content, filename="tts.wav", mime_type=result.mime_type),
            max_size_bytes=settings.media_max_size_bytes,
            allowed_mime_types=settings.media_allowed_mime_types,
            max_duration_seconds=settings.media_max_duration_seconds,
        )
    except AudioValidationError as exc:
        return {
            **base,
            "status": "FAILED",
            "reason": f"invalid TTS audio: {exc}",
            "tts_latency_ms": tts_latency_ms,
            "retries": retries,
        }

    audio = AudioReference(content=result.content, filename="tts.wav", mime_type=result.mime_type)
    ok_asr, asr_result, asr_latency_ms, asr_retries = await _transcribe_with_retry(
        asr_provider, audio, max_retries
    )
    if not ok_asr or not (asr_result.text or "").strip():
        return {
            **base,
            "status": "FAILED" if not ok_asr else "EMPTY_AUDIO",
            "reason": str(asr_result),
            "tts_latency_ms": tts_latency_ms,
            "asr_latency_ms": asr_latency_ms,
            "retries": retries,
            "asr_retries": asr_retries,
            "audio_metadata": {
                "audio_hash": _audio_hash(result.content),
                "mime_type": metadata.mime_type,
                "size_bytes": metadata.size_bytes,
                "duration_ms": metadata.duration_ms,
            },
        }

    raw_text = asr_result.text
    norm = _normalize_result(raw_text)
    return {
        **base,
        "status": "SUCCESS",
        "tts_latency_ms": tts_latency_ms,
        "asr_latency_ms": asr_latency_ms,
        "retries": retries,
        "asr_retries": asr_retries,
        "audio_metadata": {
            "audio_hash": _audio_hash(result.content),
            "mime_type": metadata.mime_type,
            "size_bytes": metadata.size_bytes,
            "duration_ms": metadata.duration_ms,
        },
        "raw_transcript": raw_text,
        "round_trip_raw_similarity": text_similarity(case["text"], raw_text),
        "round_trip_norm_similarity": text_similarity(case["text"], norm["normalized_text"]),
        "round_trip_term_accuracy": term_accuracy(norm["normalized_text"], case["expected_terms"]),
        **norm,
    }


def _write_artifacts(output_dir: Path, run_id: str, payload: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in [
        "manifest.json",
        "results.json",
        "metrics.json",
        "failures.json",
        "normalization-errors.json",
        "report.md",
    ]:
        (output_dir / name).write_text(payload[name], encoding="utf-8")
    return output_dir


def _report_markdown(
    run_id: str,
    dataset_version: str,
    metrics: dict[str, Any],
    asr_results: list[dict[str, Any]],
    tts_results: list[dict[str, Any]],
) -> str:
    lines = [
        f"# Speech Qualification Report — {run_id}",
        "",
        f"- Dataset version: `{dataset_version}`",
        f"- Normalizer ruleset version: `{NORMALIZER_RULESET_VERSION}`",
        f"- Vocabulary version: `{VOCABULARY_VERSION}`",
        "",
        "## ASR metrics",
        "",
        "```json",
        json.dumps(metrics.get("asr", {}), ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## TTS metrics",
        "",
        "```json",
        json.dumps(metrics.get("tts", {}), ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Not-evaluated / failed cases",
        "",
    ]
    skipped = [r for r in asr_results + tts_results if r.get("status") in {"SKIPPED", "FAILED", "EMPTY", "EMPTY_AUDIO"}]
    if skipped:
        for r in skipped:
            lines.append(f"- `{r['case_id']}` {r.get('status')}: {r.get('reason', '')}")
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


async def run_qualification(
    *,
    run_id: str,
    output_dir: Path,
    settings: Settings,
    audio_dir: Path | None = None,
    provider_kind: str = "mimo",
    max_retries: int = 2,
    asr_only: bool = False,
    tts_only: bool = False,
    max_cases: int | None = None,
) -> Path:
    asr_provider, tts_provider = _build_providers(settings, provider_kind)
    asr_cases = ASR_CASES if not tts_only else []
    tts_cases = TTS_CASES if not asr_only else []
    if max_cases is not None:
        asr_cases = asr_cases[:max_cases]
        tts_cases = tts_cases[:max_cases]

    asr_results: list[dict[str, Any]] = []
    for case in asr_cases:
        result = await run_asr_case(
            case,
            asr_provider=asr_provider,
            tts_provider=tts_provider,
            settings=settings,
            audio_dir=audio_dir,
            max_retries=max_retries,
        )
        asr_results.append(result)
        print(f"[ASR] {case['case_id']} -> {result['status']}")

    tts_results: list[dict[str, Any]] = []
    for case in tts_cases:
        result = await run_tts_case(
            case,
            tts_provider=tts_provider,
            asr_provider=asr_provider,
            settings=settings,
            max_retries=max_retries,
        )
        tts_results.append(result)
        print(f"[TTS] {case['case_id']} -> {result['status']}")

    asr_metrics = summarize_asr(asr_results)
    tts_metrics = summarize_tts(tts_results)
    metrics = {"asr": asr_metrics, "tts": tts_metrics, "generated_at": datetime.now(UTC).isoformat()}

    asr_cases_manifest = [
        {k: v for k, v in case.items() if k != "text"} | {"text_hash": _audio_hash(case["text"].encode("utf-8"))}
        for case in asr_cases
    ]
    tts_cases_manifest = [
        {k: v for k, v in case.items() if k != "text"} | {"text_hash": _audio_hash(case["text"].encode("utf-8"))}
        for case in tts_cases
    ]
    manifest = build_manifest(
        run_id=run_id,
        dataset_version=DATASET_VERSION,
        normalizer_ruleset_version=NORMALIZER_RULESET_VERSION,
        vocabulary_version=VOCABULARY_VERSION,
        asr_cases=asr_cases_manifest,
        tts_cases=tts_cases_manifest,
    )

    def _case_label(result: dict[str, Any]) -> str:
        return f"{result['case_id']} [{result.get('category')}] {result.get('status')}"

    failures = [
        {k: v for k, v in result.items() if k in {"case_id", "category", "status", "reason", "error_code"}}
        for result in asr_results + tts_results
        if result.get("status") in {"FAILED", "EMPTY", "EMPTY_AUDIO"}
    ]
    normalization_errors = [
        {
            "case_id": result["case_id"],
            "raw_transcript": result.get("raw_transcript"),
            "normalized_text": result.get("normalized_text"),
            "false_corrections": result.get("false_corrections") or [],
            "warnings": result.get("warnings") or [],
        }
        for result in asr_results
        if result.get("status") == "SUCCESS" and (result.get("false_corrections") or result.get("warnings"))
    ]

    payload = {
        "manifest.json": manifest,
        "results.json": json.dumps(
            {"run_id": run_id, "asr_results": redact(asr_results), "tts_results": redact(tts_results)},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        "metrics.json": json.dumps(redact(metrics), ensure_ascii=False, indent=2, sort_keys=True),
        "failures.json": json.dumps(redact(failures), ensure_ascii=False, indent=2, sort_keys=True),
        "normalization-errors.json": json.dumps(
            redact(normalization_errors), ensure_ascii=False, indent=2, sort_keys=True
        ),
        "report.md": _report_markdown(run_id, DATASET_VERSION, metrics, asr_results, tts_results),
    }
    return _write_artifacts(output_dir / run_id, run_id, payload)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sprint 1B Speech Qualification runner")
    parser.add_argument("--run-id", default="2026-08-16-s1b-qual-v1")
    parser.add_argument("--audio-dir", type=Path, default=None, help="external human-speech audio dir")
    parser.add_argument("--provider", choices=["mimo", "fake"], default="mimo")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--asr-only", action="store_true")
    parser.add_argument("--tts-only", action="store_true")
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/qualification/speech"))
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    settings = get_settings()
    if args.provider == "mimo" and not (settings.mimo_api_key and settings.mimo_api_key.get_secret_value()):
        print("MIMO_API_KEY=NOT_CONFIGURED; refusing real provider run")
        return 2
    output = asyncio.run(
        run_qualification(
            run_id=args.run_id,
            output_dir=args.output_root,
            settings=settings,
            audio_dir=args.audio_dir,
            provider_kind=args.provider,
            max_retries=args.max_retries,
            asr_only=args.asr_only,
            tts_only=args.tts_only,
            max_cases=args.max_cases,
        )
    )
    print(f"ARTIFACTS={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
