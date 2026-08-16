"""Deterministic metric helpers for Speech Qualification runs.

These pure functions are shared by the qualification harness
(``backend/scripts/speech_qualification/``) and the regression tests so that metric
calculation is reviewable and version-controlled (docs/TESTING.md §4).
"""

from __future__ import annotations

import difflib
import json
from collections.abc import Iterable
from typing import Any


def text_similarity(reference: str, candidate: str) -> float:
    """Character-level similarity (0..1) via difflib SequenceMatcher, case-insensitive."""
    left = (reference or "").strip().lower()
    right = (candidate or "").strip().lower()
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return difflib.SequenceMatcher(None, left, right).ratio()


def term_accuracy(text: str, expected_terms: Iterable[str]) -> float:
    """Fraction of expected terms present in text (case-insensitive substring match)."""
    terms = list(expected_terms or [])
    if not terms:
        return 1.0
    haystack = (text or "").lower()
    hits = sum(1 for term in terms if term.lower() in haystack)
    return hits / len(terms)


def percentile(values: list[float], percent: float) -> float:
    """Linear-interpolation percentile (P50/P95) over a list of floats."""
    ordered = sorted(v for v in values if v is not None)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return float(ordered[0])
    k = (len(ordered) - 1) * (percent / 100.0)
    lower = int(k)
    upper = min(lower + 1, len(ordered) - 1)
    weight = k - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def p50(values: list[float]) -> float:
    return percentile(values, 50)


def p95(values: list[float]) -> float:
    return percentile(values, 95)


def detect_false_corrections(gold_text: str, mappings: Iterable[Any]) -> list[dict[str, Any]]:
    """Flag mappings that introduced a fragment absent from gold and not traceable to it.

    A mapping is a false correction when neither the raw fragment nor the normalized
    fragment appears in the gold text — i.e. the normalizer rewrote something into a term
    the reference never contained. These must be surfaced for human review, never silently
    accepted (docs/speech-production.md §6).
    """
    gold = (gold_text or "").lower()
    false: list[dict[str, Any]] = []
    for mapping in mappings:
        raw = (mapping.raw_fragment or "").lower()
        normalized = (mapping.normalized_fragment or "").lower()
        if raw in gold or normalized in gold:
            continue
        false.append(
            {
                "raw_fragment": mapping.raw_fragment,
                "normalized_fragment": mapping.normalized_fragment,
                "normalization_rule": mapping.normalization_rule,
                "confidence": float(mapping.confidence),
                "reason": "normalized fragment absent from gold text",
            }
        )
    return false


def _avg(values: Iterable[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return round(sum(present) / len(present), 4)


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def summarize_asr(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-case ASR qualification results into the metrics contract."""
    evaluated = [r for r in results if r.get("status") in {"SUCCESS", "EMPTY", "FAILED"}]
    success = [r for r in results if r.get("status") == "SUCCESS"]
    empty = [r for r in results if r.get("status") == "EMPTY"]
    failed = [r for r in results if r.get("status") == "FAILED"]
    skipped = [r for r in results if r.get("status") == "SKIPPED"]
    latencies = [r["latency_ms"] for r in success if r.get("latency_ms") is not None]

    raw_term = _avg(r.get("raw_term_accuracy") for r in success)
    norm_term = _avg(r.get("norm_term_accuracy") for r in success)
    false_corrections = sum(len(r.get("false_corrections") or []) for r in success)
    review_required = sum(
        1
        for r in evaluated
        if r.get("status") in {"EMPTY", "FAILED"} or (r.get("warnings") or [])
    )
    retried = sum(1 for r in evaluated if (r.get("retries") or 0) > 0)

    return {
        "evaluated_count": len(evaluated),
        "success_count": len(success),
        "empty_count": len(empty),
        "failed_count": len(failed),
        "skipped_count": len(skipped),
        "request_success_rate": _rate(len(success), len(evaluated)),
        "non_empty_transcript_rate": _rate(len(success), len(evaluated)),
        "empty_transcript_rate": _rate(len(empty), len(evaluated)),
        "terminal_failure_rate": _rate(len(failed), len(evaluated)),
        "raw_text_similarity": _avg(r.get("raw_similarity") for r in success),
        "normalized_text_similarity": _avg(r.get("norm_similarity") for r in success),
        "raw_aviation_term_accuracy": raw_term,
        "normalized_aviation_term_accuracy": norm_term,
        "normalization_improvement": (
            round(norm_term - raw_term, 4)
            if raw_term is not None and norm_term is not None
            else None
        ),
        "false_correction_count": false_corrections,
        "false_correction_rate": _rate(false_corrections, len(success)),
        "review_required_rate": _rate(review_required, len(evaluated)),
        "retry_rate": _rate(retried, len(evaluated)),
        "latency_ms_p50": p50(latencies),
        "latency_ms_p95": p95(latencies),
    }


def summarize_tts(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-case TTS qualification results into the metrics contract."""
    evaluated = [r for r in results if r.get("status") in {"SUCCESS", "EMPTY_AUDIO", "FAILED"}]
    success = [r for r in results if r.get("status") == "SUCCESS"]
    empty_audio = [r for r in results if r.get("status") == "EMPTY_AUDIO"]
    failed = [r for r in results if r.get("status") == "FAILED"]
    skipped = [r for r in results if r.get("status") == "SKIPPED"]
    latencies = [r["tts_latency_ms"] for r in success if r.get("tts_latency_ms") is not None]

    return {
        "evaluated_count": len(evaluated),
        "success_count": len(success),
        "empty_audio_count": len(empty_audio),
        "failed_count": len(failed),
        "skipped_count": len(skipped),
        "api_success_rate": _rate(len(success), len(evaluated)),
        "valid_audio_rate": _rate(len(success), len(evaluated)),
        "empty_audio_rate": _rate(len(empty_audio), len(evaluated)),
        "failure_rate": _rate(len(failed), len(evaluated)),
        "round_trip_raw_similarity": _avg(r.get("round_trip_raw_similarity") for r in success),
        "round_trip_norm_similarity": _avg(r.get("round_trip_norm_similarity") for r in success),
        "round_trip_term_accuracy": _avg(r.get("round_trip_term_accuracy") for r in success),
        "latency_ms_p50": p50(latencies),
        "latency_ms_p95": p95(latencies),
        "retry_rate": _rate(sum(1 for r in evaluated if (r.get("retries") or 0) > 0), len(evaluated)),
    }


def build_manifest(
    *,
    run_id: str,
    dataset_version: str,
    normalizer_ruleset_version: str,
    vocabulary_version: str,
    asr_cases: list[dict[str, Any]],
    tts_cases: list[dict[str, Any]],
) -> str:
    """Deterministic, reviewable manifest JSON (no audio, no secrets)."""
    manifest = {
        "run_id": run_id,
        "dataset_version": dataset_version,
        "normalizer_ruleset_version": normalizer_ruleset_version,
        "vocabulary_version": vocabulary_version,
        "asr_cases": asr_cases,
        "tts_cases": tts_cases,
    }
    return json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
