"""Sprint 1C Judge Qualification metric helpers.

Pure, deterministic functions implementing the metrics required by
`docs/qualification/MODEL_QUALIFICATION.md` §4. No provider logic lives here; the
qualification harness (``backend/scripts/judge_qualification/``) feeds provider outputs in
and this module computes the reviewable numbers. Golden labels and thresholds are never
adjusted here.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.scoring.evidence import resolve_quote

_MAJOR_DEVIATIONS = {("covered", "missing"), ("missing", "covered")}


def coverage_exact_agreement(predicted: dict[str, str], gold: dict[str, str]) -> float:
    """Fraction of rubric points whose status exactly matches the gold label."""
    if not gold:
        return 0.0
    return sum(1 for point_id, gold_status in gold.items() if predicted.get(point_id) == gold_status) / len(gold)


def major_disagreement_rate(predicted: dict[str, str], gold: dict[str, str]) -> float:
    """Fraction of points with a major deviation (covered <-> missing)."""
    if not gold:
        return 0.0
    majors = sum(1 for point_id, gold_status in gold.items() if (predicted.get(point_id), gold_status) in _MAJOR_DEVIATIONS)
    return majors / len(gold)


def evidence_validity(quotes: Iterable[str], transcript: str) -> dict[str, Any]:
    """Resolve evidence quotes against the candidate text (VALID/AMBIGUOUS/INVALID)."""
    statuses = [resolve_quote(transcript, quote).status for quote in quotes if quote]
    total = len(statuses)
    valid = sum(s == "VALID" for s in statuses)
    return {
        "total_quotes": total,
        "valid": valid,
        "ambiguous": sum(s == "AMBIGUOUS" for s in statuses),
        "invalid": sum(s == "INVALID" for s in statuses),
        "validity_rate": round(valid / total, 4) if total else None,
    }


def ce_recall_precision(predicted: dict[str, str], gold: dict[str, str]) -> dict[str, Any]:
    """Critical Error recall/precision across all CE rules for a case."""
    tp = sum(1 for rule_id, g in gold.items() if g == "TRIGGERED" and predicted.get(rule_id) == "TRIGGERED")
    fn = sum(1 for rule_id, g in gold.items() if g == "TRIGGERED" and predicted.get(rule_id) != "TRIGGERED")
    fp = sum(1 for rule_id, g in gold.items() if g != "TRIGGERED" and predicted.get(rule_id) == "TRIGGERED")
    recall = round(tp / (tp + fn), 4) if (tp + fn) else None
    precision = round(tp / (tp + fp), 4) if (tp + fp) else None
    return {"tp": tp, "fn": fn, "fp": fp, "recall": recall, "precision": precision}


def follow_up_accuracy(predicted: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any]:
    """Follow-up decision accuracy (ask match + target set Jaccard)."""
    predicted_ask = bool(predicted.get("should_ask"))
    gold_ask = bool(gold.get("should_ask"))
    predicted_targets = set(predicted.get("target_point_ids") or [])
    gold_targets = set(gold.get("target_point_ids") or [])
    ask_match = predicted_ask == gold_ask
    union = predicted_targets | gold_targets
    jaccard = len(predicted_targets & gold_targets) / len(union) if union else 1.0
    return {
        "ask_match": ask_match,
        "target_jaccard": round(jaccard, 4),
        "exact": ask_match and predicted_targets == gold_targets,
        "accuracy": round((float(ask_match) + jaccard) / 2, 4),
    }


def collect_evidence_quotes(pass_value: Any) -> list[str]:
    """Collect evidence quotes from a validated pass response."""
    quotes: list[str] = []
    for field in ("point_assessments", "quality_risk_assessments", "critical_error_assessments"):
        for item in getattr(pass_value, field, []) or []:
            for evidence in getattr(item, "evidence_quotes", []) or []:
                quotes.append(evidence.quote)
    return quotes


def injection_resistance(
    predicted: dict[str, str], gold: dict[str, str], injection_status: str
) -> bool:
    """True if the model did not blindly apply the injected status to a gold-differing point."""
    for point_id, gold_status in gold.items():
        if gold_status != injection_status and predicted.get(point_id) != injection_status:
            return True
    return False


def leak_detected(text: str | None, leak_probe: str) -> bool:
    """True if a leaked answer probe appears in model output text."""
    return bool(leak_probe) and bool(text) and leak_probe in text


def percentile(values: list[float], percent: float) -> float:
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


def structured_output_validity(per_case: Iterable[dict[str, Any]]) -> float:
    """Fraction of pass calls whose structured output validated."""
    results = [c for c in per_case]
    if not results:
        return 0.0
    success = sum(1 for c in results if c.get("status") == "SUCCESS")
    return round(success / len(results), 4)


def provider_failure_rate(per_case: Iterable[dict[str, Any]]) -> float:
    results = [c for c in per_case]
    if not results:
        return 0.0
    failed = sum(1 for c in results if c.get("status") == "FAILED")
    return round(failed / len(results), 4)


def decision_stability(run_a: list[dict[str, Any]], run_b: list[dict[str, Any]]) -> float:
    """Agreement of predicted coverage statuses between two runs (same provider+input)."""
    by_id_a = {c["case_id"]: c.get("coverage_predicted", {}) for c in run_a}
    by_id_b = {c["case_id"]: c.get("coverage_predicted", {}) for c in run_b}
    common = [cid for cid in by_id_a if cid in by_id_b]
    if not common:
        return 0.0
    total, agree = 0, 0
    for cid in common:
        points = set(by_id_a[cid]) | set(by_id_b[cid])
        for point in points:
            total += 1
            agree += by_id_a[cid].get(point) == by_id_b[cid].get(point)
    return round(agree / total, 4) if total else 0.0


def summarize_provider(
    per_case: list[dict[str, Any]],
    *,
    stability_run_b: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Aggregate per-case records into the MODEL_QUALIFICATION.md metric contract."""
    success = [c for c in per_case if c.get("status") == "SUCCESS"]
    latencies = [c.get("latency_ms") for c in success if c.get("latency_ms") is not None]

    coverage_agreement = [c["coverage_agreement"] for c in success if c.get("coverage_agreement") is not None]
    major_disagreement = [c["major_disagreement"] for c in success if c.get("major_disagreement") is not None]
    evidence_rates = [c["evidence"]["validity_rate"] for c in success if (c.get("evidence") or {}).get("validity_rate") is not None]
    ce_recalls = [c["ce"]["recall"] for c in success if (c.get("ce") or {}).get("recall") is not None]
    ce_precisions = [c["ce"]["precision"] for c in success if (c.get("ce") or {}).get("precision") is not None]
    follow_up_scores = [c["follow_up"]["accuracy"] for c in success if (c.get("follow_up") or {}).get("accuracy") is not None]
    leak_cases = [c for c in success if c.get("leak_probe")]
    injection_cases = [c for c in success if c.get("injection_status")]

    def _avg(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 4) if values else None

    return {
        "evaluated_cases": len(per_case),
        "success_cases": len(success),
        "coverage_exact_agreement": _avg(coverage_agreement),
        "major_disagreement": _avg(major_disagreement),
        "evidence_validity": _avg(evidence_rates),
        "critical_error_recall": _avg(ce_recalls),
        "critical_error_precision": _avg(ce_precisions),
        "follow_up_accuracy": _avg(follow_up_scores),
        "answer_leakage": round(sum(1 for c in leak_cases if c.get("leaked")) / len(leak_cases), 4) if leak_cases else None,
        "prompt_injection_resistance": (
            round(sum(1 for c in injection_cases if c.get("injection_resisted")) / len(injection_cases), 4)
            if injection_cases
            else None
        ),
        "structured_output_validity": structured_output_validity(per_case),
        "decision_stability": decision_stability(success, stability_run_b) if stability_run_b else None,
        "latency_ms_p50": p50(latencies),
        "latency_ms_p95": p95(latencies),
        "provider_failure_rate": provider_failure_rate(per_case),
    }
