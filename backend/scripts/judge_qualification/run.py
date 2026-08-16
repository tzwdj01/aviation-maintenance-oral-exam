"""Sprint 1C Judge Qualification runner (Formal-Run Ready, harness v2).

Usage:
    python -m scripts.judge_qualification.run --providers mimo,deepseek [--fake]
        --run-id <id> --output-root artifacts/qualification/judge --stability-runs 3
    python -m scripts.judge_qualification.run --providers mimo,deepseek
        --run-id <id> --output-root artifacts/qualification/judge --resume
    python -m scripts.judge_qualification.run --providers mimo,deepseek
        --run-id <id> --output-root artifacts/qualification/judge --reassemble-only

Formal-run invariants (docs/qualification/MODEL_QUALIFICATION.md):
- Every provider receives the SAME TRUSTED_EVALUATION_CONTEXT (rubric, CE rules, evidence
  rules, task-specific output contract derived from the shared Pydantic schema) and the
  candidate answer only in a separate UNTRUSTED_CANDIDATE_DATA boundary.
- A SMOKE stage must pass before the full run; failure => PROVIDER_SMOKE_FAILED.
- Each stability case is run >=3 times; decision stability covers coverage + CE + follow-up.
- The manifest pins golden/prompt/schema hashes + gate version + harness version + code
  commit + a stability-subset hash; providers must share the same hashes or the run is
  QUALIFICATION_INVALID_RUN.

Harness v2 — checkpoint / resume (Sprint 1C reliability):
- Every case-run (provider + case_id + stability_run_number) is atomically persisted to
  ``checkpoints/<provider>/<case_id>/run-<n>.json`` immediately after it completes
  (temp file -> fsync/close -> atomic replace). No case-run work is lost if the process
  terminates mid-run.
- ``--resume`` revalidates EVERY existing checkpoint against the current frozen inputs
  (golden version+hash, prompt bundle version+hash, schema version+hash, gate version,
  stability-subset hash, harness version, provider, exact model). Any mismatch ->
  REFUSE_RESUME / QUALIFICATION_RESUME_MISMATCH; old checkpoints are never mixed into a
  new run.
- Completed persisted case-runs are SKIP_COMPLETED (no provider call). An incomplete
  case-run is re-executed in full (case-run is the atomic unit; no partial-pass recovery).
- When all case-runs are present, results.json / metrics.json / failures.json /
  decision-stability / report.md / manifest.json are rebuilt deterministically from the
  checkpoints (``--reassemble-only`` rebuilds without any provider call).
- Checkpoints never contain credentials: every persisted payload is ``redact()``-ed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
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
    MODEL_QUALIFICATION_GATE_VERSION,
    ce_recall_precision,
    collect_evidence_quotes,
    coverage_exact_agreement,
    decision_stability_multipass,
    evaluate_model_qualification,
    evidence_validity,
    follow_up_accuracy,
    golden_dataset_hash,
    guard_run_validity,
    injection_resistance,
    leak_detected,
    major_disagreement_rate,
    prompt_bundle_hash,
    schema_hash,
    stability_subset_hash,
    stability_subset_size,
    summarize_provider,
)

from scripts.judge_qualification.golden import DATASET_VERSION, GOLDEN_CASES, PROMPT_BUNDLE_VERSION
from scripts.judge_qualification.prompts import prompt_bundle_snapshot, system_prompt_for

TASK_TYPES = ("COVERAGE", "CRITICAL_ERROR", "QUALITY_RISK", "FOLLOW_UP", "FINAL_ASSESSMENT")
PRIOR_CHAIN = ("COVERAGE", "CRITICAL_ERROR", "QUALITY_RISK", "FOLLOW_UP")
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
SCHEMA_VERSION = "eval-schema-v1"
JUDGE_QUALIFICATION_HARNESS_VERSION = "judge-harness-v2"

# Fields that define Qualification semantics and therefore gate resume compatibility.
# ``code_commit_sha`` is recorded for audit only; the compatible resume marker is the
# harness version (a code change that alters Qualification semantics must bump it).
FROZEN_RESUME_FIELDS = (
    "golden_dataset_version",
    "golden_dataset_hash",
    "prompt_bundle_version",
    "prompt_bundle_hash",
    "schema_version",
    "schema_hash",
    "qualification_gate_version",
    "stability_subset_hash",
    "harness_version",
)

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


class QualificationResumeMismatch(RuntimeError):
    """Frozen qualification inputs changed since a checkpoint was written (REFUSE_RESUME)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.code = "QUALIFICATION_RESUME_MISMATCH"


@dataclass(frozen=True)
class FrozenInputs:
    """Immutable snapshot of every input that defines a Formal Run's semantics."""

    golden_dataset_version: str
    golden_dataset_hash: str
    prompt_bundle_version: str
    prompt_bundle_hash: str
    schema_version: str
    schema_hash: str
    qualification_gate_version: str
    stability_subset_size: int
    stability_subset_ids: list[str]
    stability_subset_hash: str
    harness_version: str
    code_commit_sha: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _build_frozen_inputs(
    *,
    golden_hash: str,
    bundle_hash: str,
    schema_hash_value: str,
    stability_size: int,
    stability_ids: list[str],
    commit_sha: str,
) -> FrozenInputs:
    return FrozenInputs(
        golden_dataset_version=DATASET_VERSION,
        golden_dataset_hash=golden_hash,
        prompt_bundle_version=PROMPT_BUNDLE_VERSION,
        prompt_bundle_hash=bundle_hash,
        schema_version=SCHEMA_VERSION,
        schema_hash=schema_hash_value,
        qualification_gate_version=MODEL_QUALIFICATION_GATE_VERSION,
        stability_subset_size=stability_size,
        stability_subset_ids=stability_ids,
        stability_subset_hash=stability_subset_hash(GOLDEN_CASES, stability_size),
        harness_version=JUDGE_QUALIFICATION_HARNESS_VERSION,
        code_commit_sha=commit_sha,
    )


def _checkpoint_root(output_dir: Path, run_id: str) -> Path:
    return output_dir / run_id / "checkpoints"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically: temp file -> fsync/close -> atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _load_checkpoint(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _smoke_checkpoint_path(provider_dir: Path) -> Path:
    return provider_dir / "smoke.json"


def _case_checkpoint_path(provider_dir: Path, case_id: str, run_number: int) -> Path:
    return provider_dir / case_id / f"run-{run_number}.json"


def _validate_frozen(stored: dict[str, Any], current: FrozenInputs) -> str | None:
    """Return a description of the first frozen-input mismatch, or None if compatible."""
    for field in FROZEN_RESUME_FIELDS:
        if stored.get(field) != getattr(current, field):
            return f"{field}: checkpoint={stored.get(field)!r} current={getattr(current, field)!r}"
    return None


def _validate_resume_checkpoints(
    checkpoint_root: Path,
    frozen: FrozenInputs,
    model_by_provider: dict[str, str],
) -> None:
    """Validate every existing checkpoint's provider/model/frozen inputs (REFUSE_RESUME).

    Any mismatch raises QualificationResumeMismatch; old checkpoints are never mixed into
    a new Formal Run.
    """
    if not checkpoint_root.exists():
        return
    problems: list[str] = []
    for provider_dir in sorted(checkpoint_root.iterdir()):
        if not provider_dir.is_dir():
            continue
        provider = provider_dir.name
        for path in sorted(provider_dir.rglob("*.json")):
            checkpoint = _load_checkpoint(path)
            if checkpoint is None:
                problems.append(f"{path}: unreadable checkpoint")
                continue
            stored_provider = checkpoint.get("provider")
            stored_model = checkpoint.get("model")
            stored_frozen = checkpoint.get("frozen_inputs") or {}
            if stored_provider != provider:
                problems.append(f"{path}: provider={stored_provider!r} != dir {provider!r}")
            expected_model = model_by_provider.get(provider)
            if expected_model is not None and stored_model != expected_model:
                problems.append(f"{path}: model={stored_model!r} != current {expected_model!r}")
            mismatch = _validate_frozen(stored_frozen, frozen)
            if mismatch is not None:
                problems.append(f"{path}: {mismatch}")
    if problems:
        raise QualificationResumeMismatch("; ".join(problems))


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001 - non-git context
        return "unknown"


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


def _model_for(settings: Settings, provider: str) -> str:
    return {
        "mimo": settings.mimo_llm_model,
        "deepseek": settings.deepseek_default_model,
        "openai": settings.openai_default_model,
        "fake": "fake-evaluation-v1",
    }[provider]


def _build_request(case: dict[str, Any], task_type: str, *, prior_analysis: dict[str, Any] | None = None) -> EvaluationRequest[Any]:
    return EvaluationRequest(
        task_type=task_type,
        system_prompt=system_prompt_for(task_type),
        candidate_text=case["candidate_text"],
        rubric_snapshot=case["rubric_snapshot"],
        output_type=OUTPUT_TYPES[task_type],
        prompt_version=case["prompt_version"],
        question_text=case["question_text"],
        critical_error_rules=tuple(case["critical_error_rules"]),
        prior_analysis=prior_analysis,
    )


def _prior_view(task_type: str, value: Any) -> dict[str, Any]:
    if task_type == "COVERAGE":
        return {"point_status": {a.point_id: a.status for a in value.point_assessments}}
    if task_type == "CRITICAL_ERROR":
        return {"critical_error_result": {a.critical_error_id: a.result for a in value.critical_error_assessments}}
    if task_type == "QUALITY_RISK":
        return {"quality_risk_status": {a.point_id: a.status for a in value.quality_risk_assessments}}
    if task_type == "FOLLOW_UP":
        return {"should_ask": value.should_ask, "target_point_ids": value.target_point_ids}
    return {}


def _output_text(pass_results: dict[str, Any]) -> str:
    parts: list[str] = []
    for value in pass_results.values():
        for field in ("point_assessments", "quality_risk_assessments", "critical_error_assessments"):
            for item in getattr(value, field, []) or []:
                parts.append(getattr(item, "reason", ""))
        parts.append(getattr(value, "follow_up_question", "") or "")
        parts.append(getattr(value, "qualitative_summary", "") or "")
    return "\n".join(parts)


async def _run_case_once(provider: Any, case: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"case_id": case["case_id"], "scenario": case["scenario"]}
    pass_results: dict[str, Any] = {}
    pass_latencies: dict[str, int] = {}
    prior: dict[str, Any] = {}
    for task_type in TASK_TYPES:
        request = _build_request(case, task_type, prior_analysis=prior or None)
        started = time.monotonic()
        try:
            response = await getattr(provider, PROVIDER_METHOD[task_type])(request)
        except ProviderFailure as exc:
            return {
                **result,
                "status": "FAILED",
                "failed_pass": task_type,
                "error": str(exc),
                "pass_status": {t: ("SUCCESS" if t in pass_results else "NOT_RUN") for t in TASK_TYPES},
                "latency_ms": round(sum(pass_latencies.values()) / len(pass_latencies)) if pass_latencies else None,
            }
        pass_latencies[task_type] = int((time.monotonic() - started) * 1000)
        pass_results[task_type] = response.value
        if task_type in PRIOR_CHAIN:
            prior[task_type] = _prior_view(task_type, response.value)

    coverage_value = pass_results["COVERAGE"]
    coverage_predicted = {a.point_id: a.status for a in coverage_value.point_assessments}
    gold_coverage = case["gold"]["coverage"]
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
    evidence = evidence_validity(evidence_quotes, case["candidate_text"])
    output_text = _output_text(pass_results)
    result.update(
        {
            "status": "SUCCESS",
            "coverage_predicted": coverage_predicted,
            "ce_predicted": ce_predicted,
            "follow_up_predicted": fu_predicted,
            "final_predicted": {
                "initial_mastery": final_value.initial_mastery,
                "final_mastery": final_value.final_mastery,
                "prompt_dependency": final_value.prompt_dependency,
            },
            "coverage_agreement": coverage_exact_agreement(coverage_predicted, gold_coverage),
            "major_disagreement": major_disagreement_rate(coverage_predicted, gold_coverage),
            "evidence": evidence,
            "ce": ce_recall_precision(ce_predicted, case["gold"]["critical_errors"]),
            "follow_up": follow_up_accuracy(fu_predicted, case["gold"]["follow_up"]),
            "pass_latencies_ms": pass_latencies,
            "latency_ms": round(sum(pass_latencies.values()) / len(pass_latencies)),
            "leak_probe": case.get("leak_probe"),
            "leaked": leak_detected(output_text, case["leak_probe"]) if case.get("leak_probe") else False,
            "injection_status": case.get("injection_status"),
            "injection_resisted": (
                injection_resistance(coverage_predicted, gold_coverage, case["injection_status"])
                if case.get("injection_status")
                else None
            ),
            "pass_status": {task: "SUCCESS" for task in TASK_TYPES},
        }
    )
    return result


def _allowed_ids(case: dict[str, Any]) -> tuple[set[str], set[str]]:
    points = {p.get("point_id") for p in (case["rubric_snapshot"].get("points") or [])}
    ce = {r.get("critical_error_id") for r in case["critical_error_rules"]}
    return points, ce


def _zero_tolerance_failures(records: list[dict[str, Any]], cases: list[dict[str, Any]]) -> list[str]:
    by_id = {case["case_id"]: case for case in cases}
    failures: list[str] = []
    for record in records:
        if record.get("status") != "SUCCESS":
            continue
        case = by_id.get(record["case_id"])
        if case is None:
            continue
        allowed_points, allowed_ce = _allowed_ids(case)
        unknown_points = set(record.get("coverage_predicted", {})) - allowed_points
        unknown_ce = set(record.get("ce_predicted", {})) - allowed_ce
        for point in sorted(unknown_points):
            failures.append(f"{record['case_id']}: unknown rubric point ID {point}")
        for rule in sorted(unknown_ce):
            failures.append(f"{record['case_id']}: unknown critical error ID {rule}")
        if (record.get("evidence") or {}).get("invalid", 0) > 0:
            failures.append(f"{record['case_id']}: INVALID evidence on credit-bearing status")
        if record.get("leaked"):
            failures.append(f"{record['case_id']}: answer leakage")
        if record.get("injection_resisted") is False:
            failures.append(f"{record['case_id']}: prompt injection takeover")
    return failures


async def smoke_provider(provider: Any, case: dict[str, Any]) -> dict[str, Any]:
    """Pre-formal smoke: one Coverage output, schema validation, trusted rubric present."""
    request = _build_request(case, "COVERAGE")
    if hasattr(provider, "_trusted_context"):
        trusted = provider._trusted_context(request)
        rubric_ids = {p.get("point_id") for p in (case["rubric_snapshot"].get("points") or [])}
        if not any(str(pid) in trusted for pid in rubric_ids):
            return {"status": "FAIL", "reason": "trusted rubric not present in provider context"}
    started = time.monotonic()
    try:
        response = await provider.evaluate_coverage(request)
    except ProviderFailure as exc:
        return {"status": "FAIL", "reason": str(exc), "latency_ms": int((time.monotonic() - started) * 1000)}
    if not isinstance(response.value, CoverageResponse):
        return {"status": "FAIL", "reason": "coverage output did not validate"}
    return {
        "status": "PASS",
        "model": getattr(provider, "model", ""),
        "latency_ms": int((time.monotonic() - started) * 1000),
        "output_validated": True,
        "rubric_consumed": True,
    }


def _schema_hash_value() -> str:
    schemas = {name: schema.model_json_schema() for name, schema in OUTPUT_TYPES.items()}
    return schema_hash(schemas)


async def run_qualification(
    *,
    run_id: str,
    output_dir: Path,
    settings: Settings,
    providers: tuple[str, ...],
    stability_runs: int = 3,
    max_cases: int | None = None,
    resume: bool = False,
) -> Path:
    cases = GOLDEN_CASES if max_cases is None else GOLDEN_CASES[:max_cases]
    stability_size = stability_subset_size(len(GOLDEN_CASES))
    stability_ids = [case["case_id"] for case in GOLDEN_CASES[:stability_size]]
    golden_hash = golden_dataset_hash(GOLDEN_CASES)
    bundle_hash = prompt_bundle_hash(prompt_bundle_snapshot())
    schema_hash_value = _schema_hash_value()
    commit_sha = _git_head()
    generated_at = datetime.now(UTC).isoformat()
    frozen = _build_frozen_inputs(
        golden_hash=golden_hash,
        bundle_hash=bundle_hash,
        schema_hash_value=schema_hash_value,
        stability_size=stability_size,
        stability_ids=stability_ids,
        commit_sha=commit_sha,
    )
    checkpoint_root = _checkpoint_root(output_dir, run_id)
    model_by_provider = {provider: _model_for(settings, provider) for provider in providers}

    existing_checkpoints = list(checkpoint_root.rglob("*.json")) if checkpoint_root.exists() else []
    if not resume and existing_checkpoints:
        raise RuntimeError(
            f"checkpoints already exist for run {run_id} ({existing_checkpoints[0].parent}); "
            "pass --resume to continue or choose a new run_id"
        )
    if resume:
        _validate_resume_checkpoints(checkpoint_root, frozen, model_by_provider)
    manifest_path = output_dir / run_id / "manifest.json"
    if not manifest_path.exists():
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "run_status": "RUNNING",
                    "run_validity": "PENDING",
                    **frozen.as_dict(),
                    "stability_runs": stability_runs,
                    "generated_at": generated_at,
                    "providers": list(providers),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    providers_metrics: dict[str, dict[str, Any]] = {}
    per_provider_results: dict[str, Any] = {}

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
        provider_dir = checkpoint_root / provider
        smoke = await _smoke_with_checkpoint(instance, provider, provider_dir, frozen, _model_for(settings, provider))
        if smoke["status"] != "PASS":
            providers_metrics[provider] = {
                "status": "PROVIDER_SMOKE_FAILED",
                "smoke": smoke,
                "evaluated_cases": 0,
            }
            per_provider_results[provider] = []
            print(f"[{provider}] SMOKE_FAILED: {smoke.get('reason')}")
            continue
        print(f"[{provider}] smoke PASS")

        records_by_case, primary = await _run_case_runs(
            instance,
            provider,
            provider_dir,
            cases,
            stability_runs,
            frozen,
            _model_for(settings, provider),
        )

        metrics = summarize_provider(primary)
        metrics["decision_stability"] = decision_stability_multipass(records_by_case)
        metrics["evidence_invalid_count"] = sum((r.get("evidence") or {}).get("invalid", 0) for r in primary)
        zero_tolerance = _zero_tolerance_failures(primary, cases)
        conclusion = evaluate_model_qualification(metrics, zero_tolerance)
        metrics["conclusion"] = conclusion
        metrics["status"] = "RUN"
        metrics["run_validity"] = "VALID"
        metrics["stability_runs"] = stability_runs
        metrics["stability_subset_size"] = stability_size
        metrics["stability_subset_hash"] = stability_subset_hash(GOLDEN_CASES, stability_size)
        providers_metrics[provider] = metrics
        per_provider_results[provider] = {
            "provider": provider,
            "model": _model_for(settings, provider),
            "smoke_result": smoke,
            "records_by_case": records_by_case,
        }

    return _assemble_outputs(
        run_id=run_id,
        output_dir=output_dir,
        frozen=frozen,
        providers_metrics=providers_metrics,
        per_provider_results=per_provider_results,
        model_by_provider=model_by_provider,
        stability_runs=stability_runs,
        cases_count=len(cases),
        generated_at=generated_at,
    )


async def _smoke_with_checkpoint(
    instance: Any,
    provider: str,
    provider_dir: Path,
    frozen: FrozenInputs,
    model: str,
) -> dict[str, Any]:
    """Persist the smoke result so a resumed run reuses a proven PASS without another call."""
    smoke_path = _smoke_checkpoint_path(provider_dir)
    existing = _load_checkpoint(smoke_path)
    if existing is not None:
        mismatch = _validate_frozen(existing.get("frozen_inputs") or {}, frozen)
        if mismatch is not None:
            raise QualificationResumeMismatch(f"smoke checkpoint: {mismatch}")
        if existing.get("model") != model:
            raise QualificationResumeMismatch(
                f"smoke checkpoint model mismatch: {existing.get('model')!r} != {model!r}"
            )
        smoke = existing.get("smoke") or {}
        if smoke.get("status") == "PASS":
            print(f"[{provider}] smoke PASS (resumed from checkpoint)")
            return smoke
    smoke = await smoke_provider(instance, GOLDEN_CASES[0])
    _atomic_write_json(
        smoke_path,
        {
            "provider": provider,
            "model": model,
            "frozen_inputs": frozen.as_dict(),
            "smoke": redact(smoke),
        },
    )
    return smoke


async def _run_case_runs(
    instance: Any,
    provider: str,
    provider_dir: Path,
    cases: list[dict[str, Any]],
    stability_runs: int,
    frozen: FrozenInputs,
    model: str,
) -> tuple[list[list[dict[str, Any]]], list[dict[str, Any]]]:
    """Run every case-run, persisting each checkpoint atomically as it completes.

    A persisted successful/complete case-run is SKIP_COMPLETED (no provider call). An
    incomplete case-run is re-executed in full; the case-run is the atomic resume unit.
    """
    records_by_case: list[list[dict[str, Any]]] = []
    primary: list[dict[str, Any]] = []
    for case in cases:
        runs: list[dict[str, Any]] = []
        for run_index in range(1, stability_runs + 1):
            path = _case_checkpoint_path(provider_dir, case["case_id"], run_index)
            checkpoint = _load_checkpoint(path)
            if checkpoint is not None and checkpoint.get("record") is not None:
                runs.append(checkpoint["record"])
                print(f"[{provider}] {case['case_id']} run{run_index} -> SKIP_COMPLETED (resume)")
                continue
            record = await _run_case_once(instance, case)
            record = {**record, "stability_run_number": run_index}
            _atomic_write_json(
                path,
                {
                    "provider": provider,
                    "model": model,
                    "frozen_inputs": frozen.as_dict(),
                    "record": redact(record),
                },
            )
            runs.append(record)
            print(f"[{provider}] {case['case_id']} run{run_index} -> {record['status']}")
        records_by_case.append(runs)
        primary.append(runs[0])
    return records_by_case, primary


def _run_status(
    providers_metrics: dict[str, dict[str, Any]],
    per_provider_results: dict[str, Any],
    cases_count: int,
    stability_runs: int,
) -> str:
    run_providers = [p for p, m in providers_metrics.items() if m.get("status") == "RUN"]
    if not run_providers:
        return "NO_RUN_PROVIDERS"
    for provider in run_providers:
        data = per_provider_results.get(provider)
        if not isinstance(data, dict):
            return "PARTIAL"
        total = sum(len(runs) for runs in data.get("records_by_case", []))
        if total < cases_count * stability_runs:
            return "PARTIAL"
    return "COMPLETED"


def _assemble_outputs(
    *,
    run_id: str,
    output_dir: Path,
    frozen: FrozenInputs,
    providers_metrics: dict[str, dict[str, Any]],
    per_provider_results: dict[str, Any],
    model_by_provider: dict[str, str],
    stability_runs: int,
    cases_count: int,
    generated_at: str,
) -> Path:
    """Deterministically rebuild final artifacts from the (checkpoint-backed) results."""
    run_providers = [p for p, m in providers_metrics.items() if m.get("status") == "RUN"]
    if run_providers:
        identity = {
            (
                frozen.golden_dataset_hash,
                frozen.prompt_bundle_hash,
                frozen.qualification_gate_version,
                frozen.schema_version,
                frozen.schema_hash,
            )
        }
        run_validity = "VALID" if len(identity) == 1 else "QUALIFICATION_INVALID_RUN"
    else:
        run_validity = "NO_RUN_PROVIDERS"
    if run_validity != "VALID":
        for provider in run_providers:
            providers_metrics[provider]["run_validity"] = run_validity
            providers_metrics[provider]["conclusion"] = guard_run_validity(
                providers_metrics[provider].get("conclusion", {}), run_validity
            )

    manifest = {
        "run_id": run_id,
        "run_status": _run_status(providers_metrics, per_provider_results, cases_count, stability_runs),
        "run_validity": run_validity,
        "golden_dataset_version": frozen.golden_dataset_version,
        "golden_dataset_hash": frozen.golden_dataset_hash,
        "prompt_bundle_version": frozen.prompt_bundle_version,
        "prompt_bundle_hash": frozen.prompt_bundle_hash,
        "qualification_gate_version": frozen.qualification_gate_version,
        "schema_version": frozen.schema_version,
        "schema_hash": frozen.schema_hash,
        "harness_version": frozen.harness_version,
        "code_commit_sha": frozen.code_commit_sha,
        "stability_subset_size": frozen.stability_subset_size,
        "stability_subset_ids": frozen.stability_subset_ids,
        "stability_subset_hash": frozen.stability_subset_hash,
        "stability_runs": stability_runs,
        "generated_at": generated_at,
        "providers": {
            p: {
                "run_id": run_id,
                "run_validity": m.get("run_validity", m.get("status")),
                "provider": p,
                "model": model_by_provider.get(p),
                "dataset_version": frozen.golden_dataset_version,
                "dataset_hash": frozen.golden_dataset_hash,
                "prompt_bundle_version": frozen.prompt_bundle_version,
                "prompt_bundle_hash": frozen.prompt_bundle_hash,
                "gate_version": frozen.qualification_gate_version,
                "schema_version": frozen.schema_version,
                "schema_hash": frozen.schema_hash,
                "harness_version": frozen.harness_version,
                "code_commit": frozen.code_commit_sha,
                "timestamp": generated_at,
                "smoke_result": (per_provider_results.get(p) or {}).get("smoke_result"),
            }
            for p, m in providers_metrics.items()
        },
    }

    output = output_dir / run_id
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    (output / "results.json").write_text(
        json.dumps(redact(per_provider_results), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    (output / "metrics.json").write_text(
        json.dumps(redact(providers_metrics), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    failures = {}
    for provider, provider_data in per_provider_results.items():
        if not isinstance(provider_data, dict):
            failures[provider] = []
            continue
        failures[provider] = [
            {k: v for k, v in record.items() if k in {"case_id", "status", "failed_pass", "error"}}
            for records in provider_data.get("records_by_case", [])
            for record in records
            if record.get("status") == "FAILED"
        ]
    (output / "failures.json").write_text(
        json.dumps(redact(failures), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    report_lines = [f"# Sprint 1C Judge Qualification Report — {run_id}", ""]
    for provider, metrics in providers_metrics.items():
        report_lines.append(f"## {provider}")
        report_lines.append("")
        report_lines.append("```json")
        report_lines.append(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))
        report_lines.append("```")
        report_lines.append("")
    (output / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
    return output


def _load_case_checkpoints(
    provider_dir: Path,
    cases: list[dict[str, Any]],
    stability_runs: int,
) -> tuple[list[list[dict[str, Any]]], list[dict[str, Any]]] | None:
    """Rebuild records_by_case + primary strictly from persisted checkpoints."""
    if not provider_dir.exists():
        return None
    records_by_case: list[list[dict[str, Any]]] = []
    any_found = False
    for case in cases:
        runs: list[dict[str, Any]] = []
        for run_index in range(1, stability_runs + 1):
            checkpoint = _load_checkpoint(_case_checkpoint_path(provider_dir, case["case_id"], run_index))
            if checkpoint is not None and checkpoint.get("record") is not None:
                runs.append(checkpoint["record"])
                any_found = True
        records_by_case.append(runs)
    if not any_found:
        return None
    primary = [
        (runs[0] if runs else {"case_id": case["case_id"], "status": "NOT_RUN"})
        for case, runs in zip(cases, records_by_case, strict=True)
    ]
    return records_by_case, primary


def reassemble_run(
    *,
    run_id: str,
    output_dir: Path,
    settings: Settings,
    providers: tuple[str, ...],
    stability_runs: int = 3,
    max_cases: int | None = None,
) -> Path:
    """Rebuild final artifacts from persisted checkpoints without any provider call."""
    cases = GOLDEN_CASES if max_cases is None else GOLDEN_CASES[:max_cases]
    stability_size = stability_subset_size(len(GOLDEN_CASES))
    stability_ids = [case["case_id"] for case in GOLDEN_CASES[:stability_size]]
    golden_hash = golden_dataset_hash(GOLDEN_CASES)
    bundle_hash = prompt_bundle_hash(prompt_bundle_snapshot())
    schema_hash_value = _schema_hash_value()
    commit_sha = _git_head()
    generated_at = datetime.now(UTC).isoformat()
    frozen = _build_frozen_inputs(
        golden_hash=golden_hash,
        bundle_hash=bundle_hash,
        schema_hash_value=schema_hash_value,
        stability_size=stability_size,
        stability_ids=stability_ids,
        commit_sha=commit_sha,
    )
    checkpoint_root = _checkpoint_root(output_dir, run_id)
    model_by_provider = {provider: _model_for(settings, provider) for provider in providers}
    _validate_resume_checkpoints(checkpoint_root, frozen, model_by_provider)

    providers_metrics: dict[str, dict[str, Any]] = {}
    per_provider_results: dict[str, Any] = {}
    for provider in providers:
        provider_dir = checkpoint_root / provider
        loaded = _load_case_checkpoints(provider_dir, cases, stability_runs)
        if loaded is None:
            providers_metrics[provider] = {
                "status": "NOT_RUN",
                "reason": "no persisted checkpoints for reassembly",
                "evaluated_cases": 0,
            }
            per_provider_results[provider] = []
            continue
        records_by_case, primary = loaded
        smoke = (_load_checkpoint(_smoke_checkpoint_path(provider_dir)) or {}).get("smoke") or {}
        metrics = summarize_provider(primary)
        metrics["decision_stability"] = decision_stability_multipass(records_by_case)
        metrics["evidence_invalid_count"] = sum((r.get("evidence") or {}).get("invalid", 0) for r in primary)
        zero_tolerance = _zero_tolerance_failures(primary, cases)
        conclusion = evaluate_model_qualification(metrics, zero_tolerance)
        metrics["conclusion"] = conclusion
        metrics["status"] = "RUN"
        metrics["run_validity"] = "VALID"
        metrics["stability_runs"] = stability_runs
        metrics["stability_subset_size"] = stability_size
        metrics["stability_subset_hash"] = stability_subset_hash(GOLDEN_CASES, stability_size)
        providers_metrics[provider] = metrics
        per_provider_results[provider] = {
            "provider": provider,
            "model": _model_for(settings, provider),
            "smoke_result": smoke,
            "records_by_case": records_by_case,
        }

    return _assemble_outputs(
        run_id=run_id,
        output_dir=output_dir,
        frozen=frozen,
        providers_metrics=providers_metrics,
        per_provider_results=per_provider_results,
        model_by_provider=model_by_provider,
        stability_runs=stability_runs,
        cases_count=len(cases),
        generated_at=generated_at,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sprint 1C Judge Qualification runner")
    parser.add_argument("--providers", default="mimo,deepseek,openai")
    parser.add_argument("--fake", action="store_true", help="use FakeEvaluationProvider instead of real providers")
    parser.add_argument("--run-id", default="2026-08-16-s1c-judge-v2")
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/qualification/judge"))
    parser.add_argument("--stability-runs", type=int, default=3)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="resume a Formal Run from persisted checkpoints (validates frozen inputs; SKIP_COMPLETED)",
    )
    parser.add_argument(
        "--reassemble-only",
        action="store_true",
        help="rebuild final artifacts from persisted checkpoints without any provider call",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    settings = get_settings()
    providers = tuple(p.strip().lower() for p in args.providers.split(",") if p.strip())
    if args.fake:
        providers = ("fake",)
    if args.reassemble_only:
        output = reassemble_run(
            run_id=args.run_id,
            output_dir=args.output_root,
            settings=settings,
            providers=providers,
            stability_runs=args.stability_runs,
            max_cases=args.max_cases,
        )
        print(f"ARTIFACTS={output}")
        return 0
    output = asyncio.run(
        run_qualification(
            run_id=args.run_id,
            output_dir=args.output_root,
            settings=settings,
            providers=providers,
            stability_runs=args.stability_runs,
            max_cases=args.max_cases,
            resume=args.resume,
        )
    )
    print(f"ARTIFACTS={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
