"""Formal Speech Qualification runner for the Sprint 1B Speech Gate.

Usage:
    # Default dataset qualification (TTS-synthetic corpus + optional human cases)
    python -m scripts.speech_qualification.run \
        [--run-id <id>] [--provider mimo|fake] [--max-cases N]

    # Real-human (S01) qualification + remediation before/after
    python -m scripts.speech_qualification.run \
        --human-manifest <path-to-manifest.json> --audio-dir <dir-with-wav> \
        [--run-id <id>] [--provider mimo|fake]

Credentials are read from the environment via ``app.core.config.Settings`` and are never
printed or persisted. Human-speech WAVs are consumed from an external directory and are
never committed; only hashes/metadata/gold text enter the repository artifacts.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
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

DEFAULT_RULESET_VERSIONS = ("builtin-v1", "builtin-v2")

# Enhanced pronunciation guidance for aviation abbreviations and model/engine designations.
# The user message is a free-text style instruction in the official TTS contract, so this is
# a compliant way to influence pronunciation for the TTS→ASR round-trip dimension.
PRONUNCIATION_STYLE_PROMPT = (
    "请使用清晰、自然、专业的中文口试考官语气朗读。"
    "对英文缩写请逐个字母清晰读出（例如 M-E-L、A-M-M、C-D-L、M-P-D）；"
    "对机型与发动机型号请逐项清晰读出字母和数字（例如 B-737-NG、B-737-800、C-F-M-56-7B），"
    "确保字母与数字发音准确、不连读混淆。"
)

AVIATION_TERMS = [
    "AMM", "MEL", "CDL", "FIM", "TSM", "IPC", "MPD", "AD", "SB", "EO", "ETOPS", "APU",
    "B737NG", "B737-800", "A330", "CFM56", "CFM56-7B",
    "维修放行", "故障保留", "适航指令", "最低设备清单", "维修方案", "工程指令",
    "维修记录", "签署", "放行人员", "维修", "放行", "起落架", "工作单",
]

# Abbreviations whose TTS pronunciation is improved by spelling out the letters explicitly
# (deterministic pre-processing of the TTS input text — within the official TTS contract).
_ABBREVIATIONS_TO_SPELL = ("MEL", "AMM", "CDL", "FIM", "TSM", "IPC", "MPD", "EO", "ETOPS", "APU", "AD", "SB")


def spell_out_aviation(text: str) -> str:
    """Spell out aviation abbreviations (e.g. MEL -> 'M E L') before TTS synthesis."""
    result = text
    for abbreviation in _ABBREVIATIONS_TO_SPELL:
        pattern = re.compile(r"(?<![A-Za-z0-9])" + re.escape(abbreviation) + r"(?![A-Za-z0-9])")
        result = pattern.sub(" ".join(abbreviation), result)
    return result


def _audio_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _mime_for(path: Path) -> str:
    return "audio/mpeg" if path.suffix.lower() == ".mp3" else "audio/wav"


def _extract_expected_terms(gold_text: str) -> list[str]:
    lowered = (gold_text or "").lower()
    return [term for term in AVIATION_TERMS if term.lower() in lowered]


def load_human_cases(manifest_path: Path) -> list[dict[str, Any]]:
    """Load real-human speech cases from an external golden manifest (no audio in repo)."""
    entries = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if isinstance(entries, dict):
        entries = [entries]
    cases: list[dict[str, Any]] = []
    for entry in entries:
        size = int(entry.get("size_bytes") or 0)
        # Skip placeholders/invalid samples (e.g. S02's 44-byte empty file).
        if size < 1000:
            continue
        alias = str(entry.get("speaker_alias") or "HUMAN")
        cases.append(
            {
                "case_id": f"{alias}-{entry['case_id']}",
                "category": "F_human",
                "source": "human",
                "condition": str(entry.get("condition") or "NORMAL").lower(),
                "text": entry["expected_text"],
                "expected_terms": _extract_expected_terms(entry["expected_text"]),
                "audio_filename": entry["filename"],
                "speaker_alias": alias,
                "audio_manifest": {
                    "sha256": entry.get("sha256"),
                    "size_bytes": size,
                    "duration_seconds": entry.get("duration_seconds"),
                    "peak_dbfs": entry.get("peak_dbfs"),
                    "rms_dbfs": entry.get("rms_dbfs"),
                    "silence_check": entry.get("silence_check"),
                    "consent": entry.get("consent"),
                    "recorded_at": entry.get("recorded_at"),
                },
            }
        )
    return cases


def _build_tts_provider(
    settings: Settings, style_prompt: str | None, provider_kind: str = "mimo"
) -> MiMoTTSProvider | FakeSpeechProvider:
    if provider_kind == "fake" or style_prompt is None:
        return FakeSpeechProvider()
    key = settings.mimo_api_key.get_secret_value() if settings.mimo_api_key else None
    return MiMoTTSProvider(
        settings.mimo_base_url,
        key,
        settings.mimo_tts_model,
        voice=settings.mimo_tts_voice,
        style_prompt=style_prompt,
        connect_timeout_seconds=settings.ai_connect_timeout_seconds,
        request_timeout_seconds=settings.ai_request_timeout_seconds,
    )


def _build_providers(
    settings: Settings, provider_kind: str, style_prompt: str | None = None
) -> tuple[SpeechProvider, SpeechProvider]:
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
    tts = _build_tts_provider(settings, style_prompt or settings.mimo_tts_style_prompt, provider_kind)
    return asr, tts


async def _synthesize_with_retry(
    provider: SpeechProvider, text: str, voice: str | None, max_retries: int
) -> tuple[bool, Any, int, int]:
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
    if case.get("source") == "human":
        if audio_dir is None:
            return None, {}, "human audio dir not provided"
        filename = case.get("audio_filename")
        if filename:
            path = audio_dir / filename
            if not path.is_file():
                return None, {}, f"human audio missing: {filename}"
            candidates = [path]
        else:
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
        return None, {"tts_latency_ms": latency_ms, "tts_retries": retries}, f"reference TTS synthesis failed: {result}"
    reference = AudioReference(content=result.content, filename="reference.wav", mime_type=result.mime_type)
    return reference, {"audio_source": "tts_synthetic", "tts_latency_ms": latency_ms, "tts_retries": retries}, None


def _normalize_views(
    raw_text: str, gold: str, expected_terms: list[str], ruleset_versions: tuple[str, ...]
) -> dict[str, dict[str, Any]]:
    views: dict[str, dict[str, Any]] = {}
    for version in ruleset_versions:
        norm = normalize(raw_text, VocabularySnapshot(version=VOCABULARY_VERSION), ruleset_version=version)
        views[version] = {
            "normalized_text": norm.normalized_text,
            "mappings": [
                {
                    "raw_fragment": m.raw_fragment,
                    "normalized_fragment": m.normalized_fragment,
                    "start_char": m.start_char,
                    "end_char": m.end_char,
                    "confidence": m.confidence,
                    "normalization_rule": m.normalization_rule,
                }
                for m in norm.mappings
            ],
            "warnings": list(norm.warnings),
            "ruleset_version": version,
            "norm_similarity": text_similarity(gold, norm.normalized_text),
            "norm_term_accuracy": term_accuracy(norm.normalized_text, expected_terms),
            "false_corrections": detect_false_corrections(gold, norm.mappings),
        }
    return views


async def run_asr_case(
    case: dict[str, Any],
    *,
    asr_provider: SpeechProvider,
    tts_provider: SpeechProvider,
    settings: Settings,
    audio_dir: Path | None,
    max_retries: int,
    ruleset_versions: tuple[str, ...] = DEFAULT_RULESET_VERSIONS,
) -> dict[str, Any]:
    base = {
        "case_id": case["case_id"],
        "category": case["category"],
        "source": case.get("source", "tts"),
        "condition": case.get("condition", "normal"),
        "gold_text": case["text"],
        "expected_terms": case["expected_terms"],
        "speaker_alias": case.get("speaker_alias"),
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
    if case.get("audio_manifest"):
        audio_meta["manifest"] = case["audio_manifest"]

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
            "normalizations": {},
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
            "normalizations": {},
        }
    return {
        **base,
        "status": "SUCCESS",
        "latency_ms": latency_ms,
        "retries": retries,
        "audio_metadata": audio_meta,
        "raw_transcript": raw_text,
        "raw_similarity": text_similarity(case["text"], raw_text),
        "raw_term_accuracy": term_accuracy(raw_text, case["expected_terms"]),
        "normalizations": _normalize_views(raw_text, case["text"], case["expected_terms"], ruleset_versions),
    }


def _flatten_asr_result(result: dict[str, Any], version: str) -> dict[str, Any]:
    view = (result.get("normalizations") or {}).get(version, {})
    flat = {k: v for k, v in result.items() if k != "normalizations"}
    flat.update(view)
    return flat


async def run_tts_case(
    case: dict[str, Any],
    *,
    tts_provider: SpeechProvider,
    asr_provider: SpeechProvider,
    settings: Settings,
    max_retries: int,
    ruleset_versions: tuple[str, ...] = DEFAULT_RULESET_VERSIONS,
    gold_text: str | None = None,
) -> dict[str, Any]:
    base = {
        "case_id": case["case_id"],
        "category": case["category"],
        "gold_text": gold_text or case["text"],
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
        "normalizations": _normalize_views(raw_text, case["text"], case["expected_terms"], ruleset_versions),
    }


def _flatten_tts_result(result: dict[str, Any], version: str) -> dict[str, Any]:
    view = (result.get("normalizations") or {}).get(version, {})
    flat = {k: v for k, v in result.items() if k != "normalizations"}
    flat.update(
        {
            "round_trip_norm_similarity": text_similarity(result["gold_text"], view.get("normalized_text", "")),
            "round_trip_term_accuracy": view.get("norm_term_accuracy"),
            "normalized_text": view.get("normalized_text"),
            "warnings": view.get("warnings") or [],
        }
    )
    return flat


def _remediation_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    def _delta(key: str) -> float | None:
        b, a = before.get(key), after.get(key)
        if b is None or a is None:
            return None
        return round(a - b, 4)

    return {
        "normalized_aviation_term_accuracy_delta": _delta("normalized_aviation_term_accuracy"),
        "normalization_improvement_delta": _delta("normalization_improvement"),
        "raw_vs_normalized_gap_after": after.get("normalization_improvement"),
        "false_correction_count_before": before.get("false_correction_count"),
        "false_correction_count_after": after.get("false_correction_count"),
        "review_required_rate_before": before.get("review_required_rate"),
        "review_required_rate_after": after.get("review_required_rate"),
    }


def _write_artifacts(output_dir: Path, run_id: str, payload: dict[str, str]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in payload.items():
        (output_dir / name).write_text(content, encoding="utf-8")
    return output_dir


def _report_markdown(run_id: str, sections: dict[str, dict[str, Any]]) -> str:
    lines = [f"# Speech Qualification Report — {run_id}", ""]
    for title, metrics in sections.items():
        lines.append(f"## {title}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def _base_payload(
    run_id: str, *, asr_cases: list[dict[str, Any]], tts_cases: list[dict[str, Any]]
) -> dict[str, str]:
    asr_manifest = [
        {k: v for k, v in case.items() if k != "text"}
        | {"text_hash": _audio_hash(case["text"].encode("utf-8"))}
        for case in asr_cases
    ]
    tts_manifest = [
        {k: v for k, v in case.items() if k != "text"}
        | {"text_hash": _audio_hash(case["text"].encode("utf-8"))}
        for case in tts_cases
    ]
    manifest = build_manifest(
        run_id=run_id,
        dataset_version=DATASET_VERSION,
        normalizer_ruleset_version=NORMALIZER_RULESET_VERSION,
        vocabulary_version=VOCABULARY_VERSION,
        asr_cases=asr_manifest,
        tts_cases=tts_manifest,
    )
    return {"manifest.json": manifest}


async def run_s01_gate(
    *,
    run_id: str,
    output_dir: Path,
    settings: Settings,
    human_manifest: Path,
    audio_dir: Path,
    provider_kind: str = "mimo",
    max_retries: int = 2,
    ruleset_versions: tuple[str, ...] = DEFAULT_RULESET_VERSIONS,
) -> Path:
    """Run the real-human S01 ASR qualification + remediation before/after."""
    human_cases = load_human_cases(human_manifest)
    asr_provider, tts_provider = _build_providers(settings, provider_kind)
    tts_before = _build_tts_provider(settings, settings.mimo_tts_style_prompt, provider_kind)
    tts_after = _build_tts_provider(settings, PRONUNCIATION_STYLE_PROMPT, provider_kind)

    asr_results: list[dict[str, Any]] = []
    for case in human_cases:
        result = await run_asr_case(
            case,
            asr_provider=asr_provider,
            tts_provider=tts_provider,
            settings=settings,
            audio_dir=audio_dir,
            max_retries=max_retries,
            ruleset_versions=ruleset_versions,
        )
        asr_results.append(result)
        print(f"[ASR-human] {case['case_id']} -> {result['status']}")

    tts_before_results: list[dict[str, Any]] = []
    tts_after_results: list[dict[str, Any]] = []
    for case in TTS_CASES:
        before = await run_tts_case(
            case,
            tts_provider=tts_before,
            asr_provider=asr_provider,
            settings=settings,
            max_retries=max_retries,
            ruleset_versions=ruleset_versions,
        )
        after = await run_tts_case(
            case,
            tts_provider=tts_after,
            asr_provider=asr_provider,
            settings=settings,
            max_retries=max_retries,
            ruleset_versions=ruleset_versions,
        )
        tts_before_results.append(before)
        tts_after_results.append(after)
        print(f"[TTS] {case['case_id']} before={before['status']} after={after['status']}")

    payload = _gate_payload(
        run_id,
        asr_results=asr_results,
        tts_before_results=tts_before_results,
        tts_after_results=tts_after_results,
        ruleset_versions=ruleset_versions,
        human_cases=human_cases,
        tts_after_label="tts_prompt_after",
    )
    return _write_artifacts(output_dir / run_id, run_id, payload)


def _gate_payload(
    run_id: str,
    *,
    asr_results: list[dict[str, Any]],
    tts_before_results: list[dict[str, Any]],
    tts_after_results: list[dict[str, Any]],
    ruleset_versions: tuple[str, ...],
    human_cases: list[dict[str, Any]],
    tts_after_label: str = "tts_prompt_after",
) -> dict[str, str]:
    primary = ruleset_versions[-1]
    asr_metrics = {
        version: summarize_asr([_flatten_asr_result(result, version) for result in asr_results])
        for version in ruleset_versions
    }
    asr_raw = asr_metrics[primary]
    tts_before = summarize_tts([_flatten_tts_result(r, primary) for r in tts_before_results])
    tts_after = summarize_tts([_flatten_tts_result(r, primary) for r in tts_after_results])

    asr_raw_view = {
        "request_success_rate": asr_raw["request_success_rate"],
        "empty_transcript_rate": asr_raw["empty_transcript_rate"],
        "raw_aviation_term_accuracy": asr_raw["raw_aviation_term_accuracy"],
        "raw_text_similarity": asr_raw["raw_text_similarity"],
        "latency_ms_p50": asr_raw["latency_ms_p50"],
        "latency_ms_p95": asr_raw["latency_ms_p95"],
        "retry_rate": asr_raw["retry_rate"],
        "terminal_failure_rate": asr_raw["terminal_failure_rate"],
    }
    asr_normalized = {
        f"asr_normalized_{version.split('-')[-1]}": {
            k: v for k, v in asr_metrics[version].items() if k not in {"raw_aviation_term_accuracy", "raw_text_similarity"}
        }
        for version in ruleset_versions
    }
    baseline_metrics = asr_metrics[ruleset_versions[0]]
    final_metrics = asr_metrics[primary]
    normalizer_remediation = {
        "baseline": ruleset_versions[0],
        "final": primary,
        "normalized_aviation_term_accuracy_before": baseline_metrics["normalized_aviation_term_accuracy"],
        "normalized_aviation_term_accuracy_after": final_metrics["normalized_aviation_term_accuracy"],
        "normalized_aviation_term_accuracy_delta": round(
            final_metrics["normalized_aviation_term_accuracy"] - baseline_metrics["normalized_aviation_term_accuracy"], 4
        )
        if baseline_metrics["normalized_aviation_term_accuracy"] is not None
        and final_metrics["normalized_aviation_term_accuracy"] is not None
        else None,
        "raw_vs_normalized_gap_final": final_metrics["normalization_improvement"],
        "false_correction_count_before": baseline_metrics["false_correction_count"],
        "false_correction_count_after": final_metrics["false_correction_count"],
        "review_required_rate_before": baseline_metrics["review_required_rate"],
        "review_required_rate_after": final_metrics["review_required_rate"],
        "per_version": asr_metrics,
    }
    tts_pronunciation_remediation = {
        "round_trip_term_accuracy_delta": (
            round(tts_after["round_trip_term_accuracy"] - tts_before["round_trip_term_accuracy"], 4)
            if tts_before["round_trip_term_accuracy"] is not None and tts_after["round_trip_term_accuracy"] is not None
            else None
        ),
        "round_trip_raw_similarity_before": tts_before["round_trip_raw_similarity"],
        "round_trip_raw_similarity_after": tts_after["round_trip_raw_similarity"],
    }
    metrics = {
        "run_id": run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_version": DATASET_VERSION,
        "normalizer_ruleset_versions": list(ruleset_versions),
        "primary_ruleset": primary,
        "asr_raw": asr_raw_view,
        **asr_normalized,
        "normalizer_remediation": normalizer_remediation,
        "tts_before": tts_before,
        tts_after_label: tts_after,
        "tts_pronunciation_remediation": tts_pronunciation_remediation,
    }

    failures = [
        {k: v for k, v in r.items() if k in {"case_id", "category", "status", "reason", "error_code"}}
        for r in asr_results + tts_before_results + tts_after_results
        if r.get("status") in {"FAILED", "EMPTY", "EMPTY_AUDIO"}
    ]
    normalization_errors = []
    for result in asr_results + tts_before_results + tts_after_results:
        for version, view in (result.get("normalizations") or {}).items():
            if view.get("false_corrections") or view.get("warnings"):
                normalization_errors.append(
                    {
                        "case_id": result["case_id"],
                        "ruleset_version": version,
                        "kind": "false_correction" if view.get("false_corrections") else "review_warning",
                        "raw_transcript": result.get("raw_transcript"),
                        "normalized_text": view.get("normalized_text"),
                        "false_corrections": view.get("false_corrections"),
                        "warnings": view.get("warnings"),
                    }
                )

    payload = _base_payload(run_id, asr_cases=human_cases, tts_cases=TTS_CASES)
    payload.update(
        {
            "results.json": json.dumps(
                {
                    "run_id": run_id,
                    "asr_results": redact(asr_results),
                    "tts_before": redact(tts_before_results),
                    tts_after_label: redact(tts_after_results),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            "metrics.json": json.dumps(redact(metrics), ensure_ascii=False, indent=2, sort_keys=True),
            "failures.json": json.dumps(redact(failures), ensure_ascii=False, indent=2, sort_keys=True),
            "normalization-errors.json": json.dumps(
                redact(normalization_errors), ensure_ascii=False, indent=2, sort_keys=True
            ),
            "remediation.json": json.dumps(
                redact(
                    {
                        "normalizer_before": baseline_metrics,
                        "normalizer_after": final_metrics,
                        "normalizer_delta": normalizer_remediation,
                        "tts_pronunciation_before": tts_before,
                        "tts_pronunciation_after": tts_after,
                    }
                ),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            "s01-manifest.json": json.dumps(
                redact(
                    [
                        case["audio_manifest"] | {"case_id": case["case_id"], "text": case["text"]}
                        for case in human_cases
                        if case.get("audio_manifest")
                    ]
                ),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            "report.md": _report_markdown(
                run_id,
                {
                    "ASR RAW (S01 human)": asr_raw_view,
                    **{k: v for k, v in asr_normalized.items()},
                    "Normalizer remediation": normalizer_remediation,
                    "TTS before": tts_before,
                    tts_after_label: tts_after,
                    "TTS pronunciation remediation": tts_pronunciation_remediation,
                },
            ),
        }
    )
    return payload


def recompute_normalizations(
    result: dict[str, Any], ruleset_versions: tuple[str, ...]
) -> dict[str, Any]:
    """Rebuild normalization views for a cached result from its raw transcript (no API call)."""
    if result.get("status") != "SUCCESS" or not result.get("raw_transcript"):
        result["normalizations"] = {}
        return result
    result["normalizations"] = _normalize_views(
        result["raw_transcript"],
        result.get("gold_text", ""),
        result.get("expected_terms") or [],
        ruleset_versions,
    )
    return result


async def finalize_s01_gate(
    *,
    run_id: str,
    output_dir: Path,
    settings: Settings,
    from_run: Path,
    tts_after_from: Path | None = None,
    provider_kind: str = "mimo",
    max_retries: int = 2,
    ruleset_versions: tuple[str, ...] = DEFAULT_RULESET_VERSIONS + ("builtin-v3",),
) -> Path:
    """Finalize the S01 gate: recompute normalizer before/after from cached raws and run
    the TTS spell-out pronunciation remediation for the 'after' comparison."""
    cached = json.loads((from_run / "results.json").read_text(encoding="utf-8"))
    asr_results = [recompute_normalizations(dict(result), ruleset_versions) for result in cached["asr_results"]]
    tts_before_cache = cached.get("tts_prompt_before") or cached.get("tts_before") or []
    tts_before = [recompute_normalizations(dict(result), ruleset_versions) for result in tts_before_cache]

    asr_provider, tts_provider = _build_providers(settings, provider_kind)
    if tts_after_from is not None:
        cached_after = json.loads((tts_after_from / "results.json").read_text(encoding="utf-8"))
        tts_after = [
            recompute_normalizations(dict(result), ruleset_versions)
            for result in (cached_after.get("tts_spellout_after") or [])
        ]
    else:
        tts_after = []
        for case in TTS_CASES:
            spelled = {**case, "text": spell_out_aviation(case["text"])}
            result = await run_tts_case(
                spelled,
                tts_provider=tts_provider,
                asr_provider=asr_provider,
                settings=settings,
                max_retries=max_retries,
                ruleset_versions=ruleset_versions,
                gold_text=case["text"],
            )
            tts_after.append(result)
            print(f"[TTS-spellout] {case['case_id']} -> {result['status']}")

    human_cases = [
        {
            "case_id": result["case_id"],
            "text": result.get("gold_text", ""),
            "audio_manifest": (result.get("audio_metadata") or {}).get("manifest") or {},
        }
        for result in asr_results
        if result.get("source") == "human"
    ]
    payload = _gate_payload(
        run_id,
        asr_results=asr_results,
        tts_before_results=tts_before,
        tts_after_results=tts_after,
        ruleset_versions=ruleset_versions,
        human_cases=human_cases,
        tts_after_label="tts_spellout_after",
    )
    return _write_artifacts(output_dir / run_id, run_id, payload)


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
    ruleset_version: str = NORMALIZER_RULESET_VERSION,
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
            ruleset_versions=(ruleset_version,),
        )
        asr_results.append(_flatten_asr_result(result, ruleset_version))
        print(f"[ASR] {case['case_id']} -> {result['status']}")

    tts_results: list[dict[str, Any]] = []
    for case in tts_cases:
        result = await run_tts_case(
            case,
            tts_provider=tts_provider,
            asr_provider=asr_provider,
            settings=settings,
            max_retries=max_retries,
            ruleset_versions=(ruleset_version,),
        )
        tts_results.append(_flatten_tts_result(result, ruleset_version))
        print(f"[TTS] {case['case_id']} -> {result['status']}")

    asr_metrics = summarize_asr(asr_results)
    tts_metrics = summarize_tts(tts_results)
    metrics = {
        "asr": asr_metrics,
        "tts": tts_metrics,
        "generated_at": datetime.now(UTC).isoformat(),
        "normalizer_ruleset_version": ruleset_version,
    }

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

    payload = _base_payload(run_id, asr_cases=asr_cases, tts_cases=tts_cases)
    payload.update(
        {
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
            "report.md": _report_markdown(run_id, {"ASR": asr_metrics, "TTS": tts_metrics}),
        }
    )
    return _write_artifacts(output_dir / run_id, run_id, payload)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sprint 1B Speech Qualification runner")
    parser.add_argument("--run-id", default="2026-08-16-s1b-qual-v1")
    parser.add_argument("--audio-dir", type=Path, default=None, help="external human-speech audio dir")
    parser.add_argument("--human-manifest", type=Path, default=None, help="external human golden manifest JSON")
    parser.add_argument("--provider", choices=["mimo", "fake"], default="mimo")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--asr-only", action="store_true")
    parser.add_argument("--tts-only", action="store_true")
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/qualification/speech"))
    parser.add_argument(
        "--from-run",
        type=Path,
        default=None,
        help="recompute a previous S01 run from cached raw transcripts + run TTS spell-out 'after'",
    )
    parser.add_argument(
        "--tts-after-from",
        type=Path,
        default=None,
        help="reuse cached TTS spell-out results from a previous run dir instead of re-calling the API",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    settings = get_settings()
    if args.provider == "mimo" and not (settings.mimo_api_key and settings.mimo_api_key.get_secret_value()):
        print("MIMO_API_KEY=NOT_CONFIGURED; refusing real provider run")
        return 2
    if args.human_manifest:
        if args.audio_dir is None:
            print("--human-manifest requires --audio-dir")
            return 2
        output = asyncio.run(
            run_s01_gate(
                run_id=args.run_id,
                output_dir=args.output_root,
                settings=settings,
                human_manifest=args.human_manifest,
                audio_dir=args.audio_dir,
                provider_kind=args.provider,
                max_retries=args.max_retries,
            )
        )
    elif args.from_run:
        output = asyncio.run(
            finalize_s01_gate(
                run_id=args.run_id,
                output_dir=args.output_root,
                settings=settings,
                from_run=args.from_run,
                tts_after_from=args.tts_after_from,
                provider_kind=args.provider,
                max_retries=args.max_retries,
            )
        )
    else:
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
