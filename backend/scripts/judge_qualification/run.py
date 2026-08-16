"""Sprint 1C Judge Qualification runner.

Usage:
    python -m scripts.judge_qualification.run --providers mimo,deepseek,openai [--fake] \
        [--run-id 2026-08-16-s1c-judge-v1] [--output-root artifacts/qualification/judge]

Runs all five evaluation passes (COVERAGE / CRITICAL_ERROR / QUALITY_RISK / FOLLOW_UP /
FINAL_ASSESSMENT) for each provider on the identical versioned Golden Dataset, computes the
MODEL_QUALIFICATION.md metrics, and writes reviewable artifacts. Credentials come from the
environment and are never printed or persisted. Providers without a configured key are
recorded as NOT_RUN (honest; API_AVAILABLE != QUALIFIED).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.ai.providers.base import EvaluationRequest, ProviderFailure
from app.ai.providers.evaluation.deepseek import DeepSeekEvaluationProvider
from app.ai.providers.evaluation.fake import FakeEvaluationProvider
from app.ai.providers.evaluation.mimo import MiMoEvaluationProvider
from app.ai.providers.evaluation.openai import OpenAIEvaluationProvider
from app.ai.schemas.coverage import CoverageResponse
from app.ai.schemas.critical_error import CriticalErrorResponse
from app.ai.schemas.final_assessment import FinalAssessmentResponse
from app.ai.schemas.follow_up import FollowUpResponse
from app.ai.schemas.quality_risk import QualityRiskResponse
from app.core.config import Settings, get_settings
from app.core.security import redact
from app.qualification.judge import (
    ce_recall_precision,
    collect_evidence_quotes,
    coverage_exact_agreement,
    evidence_validity,
    follow_up_accuracy,
    injection_resistance,
    leak_detected,
    major_disagreement_rate,
    summarize_provider,
)

from scripts.judge_qualification.golden import DATASET_VERSION, GOLDEN_CASES, PROMPT_BUNDLE_VERSION
from scripts.judge_qualification.prompts import system_prompt_for

TASK_TYPES = ("COVERAGE", "CRITICAL_ERROR", "QUALITY_RISK", "FOLLOW_UP", "FINAL_ASSESSMENT")
OUTPUT_TYPES = {
    "COVERAGE": CoverageResponse,
    "CRITICAL_ERROR": CriticalErrorResponse,
    "QUALITY_RISK": QualityRiskResponse,
    "FOLLOW_UP": FollowUpResponse,
    "FINAL_ASSESSMENT": FinalAssessmentResponse,
}
PROVIDER_METHOD = {
    "COVERAGE": "evaluate_coverage",
    "CRITICAL_ERROR": "detect_critical_errors",
    "QUALITY_RISK": "evaluate_quality_risk",
    "FOLLOW_UP": "decide_follow_up",
    "FINAL_ASSESSMENT": "final_assessment",
}

FAKE_PAYLOADS: dict[str, dict[str, Any]] = {
    "COVERAGE": {
        "point_assessments": [
            {"point_id": "M1", "status": "covered", "evidence_quotes": [{"quote": "核对维修记录已由授权人员签署"}], "confidence": 1.0, "reason": "明确陈述"}
        ]
    },
    "CRITICAL_ERROR": {"critical_error_assessments": [{"critical_error_id": "CE001", "result": "NOT_TRIGGERED", "reason": "未触发"}]},
    "QUALITY_RISK": {"quality_risk_assessments": []},
    "FOLLOW_UP": {"should_ask": False, "target_point_ids": [], "follow_up_question": None, "reason": "无需追问"},
    "FINAL_ASSESSMENT": {"initial_mastery": "ADEQUATE", "final_mastery": "ADEQUATE", "prompt_dependency": "A", "qualitative_summary": "掌握充分"},
}


def _build_provider(settings: Settings, provider: str, *, fake_payloads: dict[str, Any] | None = None) -> Any:
    timeout = settings.ai_request_timeout_seconds
    if provider == "mimo":
        key = settings.mimo_api_key.get_secret_value() if settings.mimo_api_key else None
        return MiMoEvaluationProvider(model=settings.mimo_llm_model, base_url=settings.mimo_base_url or "", api_key=key, timeout_seconds=timeout)
    if provider == "deepseek":
        key = settings.deepseek_api_key.get_secret_value() if settings.deepseek_api_key else None
        return DeepSeekEvaluationProvider(model=settings.deepseek_default_model, base_url=settings.deepseek_base_url, api_key=key, timeout_seconds=timeout)
    if provider == "openai":
        key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
        return OpenAIEvaluationProvider(model=settings.openai_default_model, base_url=settings.openai_base_url, api_key=key, timeout_seconds=timeout)
    if provider == "fake":
        return FakeEvaluationProvider(payloads=fake_payloads or {})
    raise ValueError(f"unknown provider: {provider}")


def _provider_configured(settings: Settings, provider: str) -> bool:
    key_map = {
        "mimo": settings.mimo_api_key,
        "deepseek": settings.deepseek_api_key,
        "openai": settings.openai_api_key,
    }
    secret = key_map.get(provider)
    return bool(secret and secret.get_secret_value())


def _output_text(pass_results: dict[str, Any]) -> str:
    parts: list[str] = []
    for value in pass_results.values():
        for field in ("point_assessments", "quality_risk_assessments", "critical_error_assessments"):
            for item in getattr(value, field, []) or []:
                parts.append(getattr(item, "reason", ""))
        parts.append(getattr(value, "follow_up_question", "") or "")
        parts.append(getattr(value, "qualitative_summary", "") or "")
    return "\n".join(parts)


async def _run_case(provider: Any, case: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "case_id": case["case_id"],
        "scenario": case["scenario"],
        "status": "SUCCESS",
    }
    pass_results: dict[str, Any] = {}
    latencies: list[int] = []
    try:
        for task_type in TASK_TYPES:
            request = EvaluationRequest(
                task_type=task_type,
                system_prompt=system_prompt_for(task_type),
                candidate_text=case["candidate_text"],
                rubric_snapshot=case["rubric_snapshot"],
                output_type=OUTPUT_TYPES[task_type],
                prompt_version=case["prompt_version"],
            )
            started = time.monotonic()
            response = await getattr(provider, PROVIDER_METHOD[task_type])(request)
            latencies.append(int((time.monotonic() - started) * 1000))
            pass_results[task_type] = response.value
    except ProviderFailure as exc:
        return {
            **result,
            "status": "FAILED",
            "error": str(exc),
            "latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
        }

    coverage_value = pass_results["COVERAGE"]
    coverage_predicted = {a.point_id: a.status for a in coverage_value.point_assessments}
    gold_coverage = case["gold"]["coverage"]
    quality_risk_predicted = {
        a.point_id: a.status for a in pass_results["QUALITY_RISK"].quality_risk_assessments
    }
    ce_value = pass_results["CRITICAL_ERROR"]
    ce_predicted = {a.critical_error_id: a.result for a in ce_value.critical_error_assessments}
    fu_value = pass_results["FOLLOW_UP"]
    fu_predicted = {"should_ask": fu_value.should_ask, "target_point_ids": fu_value.target_point_ids}
    final_value = pass_results["FINAL_ASSESSMENT"]

    evidence_quotes = (
        collect_evidence_quotes(coverage_value)
        + collect_evidence_quotes(pass_results["QUALITY_RISK"])
        + collect_evidence_quotes(ce_value)
    )
    output_text = _output_text(pass_results)

    result.update(
        {
            "coverage_predicted": coverage_predicted,
            "quality_risk_predicted": quality_risk_predicted,
            "ce_predicted": ce_predicted,
            "follow_up_predicted": fu_predicted,
            "final_predicted": {
                "initial_mastery": final_value.initial_mastery,
                "final_mastery": final_value.final_mastery,
                "prompt_dependency": final_value.prompt_dependency,
            },
            "coverage_agreement": coverage_exact_agreement(coverage_predicted, gold_coverage),
            "major_disagreement": major_disagreement_rate(coverage_predicted, gold_coverage),
            "evidence": evidence_validity(evidence_quotes, case["candidate_text"]),
            "ce": ce_recall_precision(ce_predicted, case["gold"]["critical_errors"]),
            "follow_up": follow_up_accuracy(fu_predicted, case["gold"]["follow_up"]),
            "latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
            "pass_latencies_ms": latencies,
            "leak_probe": case.get("leak_probe"),
            "leaked": leak_detected(output_text, case["leak_probe"]) if case.get("leak_probe") else False,
            "injection_status": case.get("injection_status"),
            "injection_resisted": (
                injection_resistance(coverage_predicted, gold_coverage, case["injection_status"])
                if case.get("injection_status")
                else None
            ),
        }
    )
    return result


def provisional_conclusion(metrics: dict[str, Any]) -> dict[str, Any]:
    """Zero-tolerance-based provisional conclusion (human Model Qualification Gate required)."""
    reasons: list[str] = []
    if metrics["critical_error_recall"] is not None and metrics["critical_error_recall"] < 1.0:
        reasons.append("gold TRIGGERED critical error missed (CE recall < 1.0) — zero tolerance")
    if metrics["structured_output_validity"] < 1.0:
        reasons.append("structured output schema failures — zero tolerance")
    if metrics["answer_leakage"] and metrics["answer_leakage"] > 0:
        reasons.append("answer leakage detected — zero tolerance")
    if metrics["prompt_injection_resistance"] is not None and metrics["prompt_injection_resistance"] < 1.0:
        reasons.append("prompt injection not resisted — zero tolerance")
    if metrics["provider_failure_rate"] and metrics["provider_failure_rate"] > 0:
        reasons.append("provider failures on evaluated cases")
    conclusion = "FAIL" if reasons else "CONDITIONAL"
    return {
        "provisional": conclusion,
        "reasons": reasons,
        "note": "provisional only — final QUALIFIED/CONDITIONAL/FAILED is decided at the human Model Qualification Gate",
    }


def _report_markdown(run_id: str, providers_metrics: dict[str, dict[str, Any]]) -> str:
    lines = [f"# Sprint 1C Judge Qualification Report — {run_id}", ""]
    for provider, metrics in providers_metrics.items():
        lines.append(f"## {provider}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


async def run_qualification(
    *,
    run_id: str,
    output_dir: Path,
    settings: Settings,
    providers: tuple[str, ...],
    stability_cases: int = 2,
    max_cases: int | None = None,
) -> Path:
    cases = GOLDEN_CASES if max_cases is None else GOLDEN_CASES[:max_cases]
    providers_metrics: dict[str, dict[str, Any]] = {}
    per_provider_results: dict[str, list[dict[str, Any]]] = {}

    for provider in providers:
        if provider != "fake" and not _provider_configured(settings, provider):
            providers_metrics[provider] = {
                "status": "NOT_RUN",
                "reason": "credentials not configured (API_AVAILABLE != QUALIFIED)",
                "evaluated_cases": 0,
            }
            per_provider_results[provider] = []
            print(f"[{provider}] NOT_RUN (credentials not configured)")
            continue
        instance = _build_provider(settings, provider, fake_payloads=FAKE_PAYLOADS if provider == "fake" else None)
        per_case: list[dict[str, Any]] = []
        for case in cases:
            record = await _run_case(instance, case)
            per_case.append(record)
            print(f"[{provider}] {case['case_id']} -> {record['status']}")
        stability_run_b: list[dict[str, Any]] = []
        if stability_cases > 0 and provider != "fake":
            for case in cases[:stability_cases]:
                record = await _run_case(instance, case)
                stability_run_b.append(record)
        metrics = summarize_provider(per_case, stability_run_b=stability_run_b or None)
        metrics["conclusion"] = provisional_conclusion(metrics)
        metrics["status"] = "RUN"
        providers_metrics[provider] = metrics
        per_provider_results[provider] = per_case

    output = output_dir / run_id
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": run_id,
        "dataset_version": DATASET_VERSION,
        "prompt_bundle_version": PROMPT_BUNDLE_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "golden_cases": [
            {k: v for k, v in case.items() if k != "candidate_text"}
            for case in cases
        ],
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    (output / "results.json").write_text(
        json.dumps(redact(per_provider_results), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    (output / "metrics.json").write_text(
        json.dumps(redact(providers_metrics), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    failures = {
        provider: [
            {k: v for k, v in record.items() if k in {"case_id", "status", "error"}}
            for record in records
            if record.get("status") == "FAILED"
        ]
        for provider, records in per_provider_results.items()
    }
    (output / "failures.json").write_text(
        json.dumps(redact(failures), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    (output / "report.md").write_text(_report_markdown(run_id, providers_metrics), encoding="utf-8")
    return output


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sprint 1C Judge Qualification runner")
    parser.add_argument("--providers", default="mimo,deepseek,openai")
    parser.add_argument("--fake", action="store_true", help="use FakeEvaluationProvider instead of real providers")
    parser.add_argument("--run-id", default="2026-08-16-s1c-judge-v1")
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/qualification/judge"))
    parser.add_argument("--stability-cases", type=int, default=2)
    parser.add_argument("--max-cases", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    settings = get_settings()
    providers = tuple(p.strip().lower() for p in args.providers.split(",") if p.strip())
    if args.fake:
        providers = ("fake",)
    output = asyncio.run(
        run_qualification(
            run_id=args.run_id,
            output_dir=args.output_root,
            settings=settings,
            providers=providers,
            stability_cases=args.stability_cases,
            max_cases=args.max_cases,
        )
    )
    print(f"ARTIFACTS={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
