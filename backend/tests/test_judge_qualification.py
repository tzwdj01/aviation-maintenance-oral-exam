"""Sprint 1C Judge Qualification hardening regression coverage.

Covers the human review requirements (harness remediation): trusted/untrusted context
boundary, rubric actually sent, schema-contract parity across providers, frozen Gate v1
thresholds + boundaries, zero-tolerance overrides, dataset/prompt/schema hashes,
stability subset and 3-run decision stability, smoke-before-formal, invalid-run guard and
no-secret artifacts.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from app.ai.providers.base import ProviderFailure
from app.ai.providers.evaluation.deepseek import DeepSeekEvaluationProvider
from app.ai.providers.evaluation.mimo import MiMoEvaluationProvider
from app.ai.providers.evaluation.openai import OpenAIEvaluationProvider
from app.core.config import Settings
from app.core.security import redact
from app.qualification.judge import (
    MODEL_QUALIFICATION_GATE_VERSION,
    ce_recall_precision,
    content_hash,
    coverage_exact_agreement,
    decision_stability,
    decision_stability_multipass,
    evaluate_model_qualification,
    evidence_validity,
    follow_up_accuracy,
    golden_dataset_hash,
    guard_run_validity,
    injection_resistance,
    leak_detected,
    major_disagreement_rate,
    p50,
    p95,
    prompt_bundle_hash,
    provider_failure_rate,
    schema_hash,
    stability_subset_hash,
    stability_subset_size,
    structured_output_validity,
    summarize_provider,
)
from scripts.judge_qualification.golden import (
    DATASET_VERSION,
    GOLDEN_CASES,
    assert_golden_self_consistent,
)
from scripts.judge_qualification.prompts import PROMPT_BUNDLE_VERSION, prompt_bundle_snapshot
from scripts.judge_qualification.run import (
    SCHEMA_VERSION,
    _build_request,
    _schema_hash_value,
    run_qualification,
    smoke_provider,
)


def _perfect_metrics() -> dict:
    return {
        "coverage_exact_agreement": 1.0,
        "major_disagreement": 0.0,
        "evidence_validity": 1.0,
        "evidence_invalid_count": 0,
        "critical_error_recall": 1.0,
        "critical_error_precision": 1.0,
        "follow_up_accuracy": 1.0,
        "answer_leakage": 0.0,
        "prompt_injection_resistance": 1.0,
        "structured_output_validity": 1.0,
        "decision_stability": 1.0,
        "provider_failure_rate": 0.0,
        "latency_ms_p95": 100,
    }


def test_golden_dataset_is_self_consistent_and_covers_all_scenarios() -> None:
    assert_golden_self_consistent()
    case_ids = [case["case_id"] for case in GOLDEN_CASES]
    assert len(case_ids) == len(set(case_ids))
    assert DATASET_VERSION == "judge-qual-golden-v1"
    scenarios = {case["scenario"].split("_")[0] for case in GOLDEN_CASES}
    assert {"A", "B", "C", "D", "E", "F", "G", "H"} <= scenarios
    assert {case["prompt_version"] for case in GOLDEN_CASES} == {PROMPT_BUNDLE_VERSION}


def test_rubric_snapshot_is_actually_sent() -> None:
    """Review D: rubric_snapshot must reach the provider, and different rubrics differ."""
    case_a = dict(GOLDEN_CASES[0])
    case_b = dict(GOLDEN_CASES[0])
    case_b["rubric_snapshot"] = {
        "points": [
            {"point_id": "X1", "evaluation_mode": "COVERAGE", "text": "不同规则"},
            {"point_id": "X2", "evaluation_mode": "QUALITY_RISK", "text": "另一规则"},
        ]
    }
    provider = DeepSeekEvaluationProvider(model="m", base_url="https://x", api_key="k")
    content_a = provider._user_content(_build_request(case_a, "COVERAGE"))
    content_b = provider._user_content(_build_request(case_b, "COVERAGE"))
    assert "M1" in content_a and "X1" in content_b
    assert content_a != content_b


def test_trusted_untrusted_boundary() -> None:
    """Review B: trusted context (rubric/CE/schema) is separate from the candidate."""
    provider = DeepSeekEvaluationProvider(model="m", base_url="https://x", api_key="k")
    case = GOLDEN_CASES[0]
    content = provider._user_content(_build_request(case, "CRITICAL_ERROR"))
    trusted_part, untrusted_part = content.split("UNTRUSTED_CANDIDATE_DATA:")
    assert "TRUSTED_EVALUATION_CONTEXT:" in trusted_part
    assert "M1" in trusted_part and "CE001" in trusted_part
    assert "output_contract" in trusted_part
    assert case["candidate_text"] in untrusted_part
    assert "M1" not in untrusted_part


def test_schema_contract_supplied_to_json_mode_providers() -> None:
    """Review C: JSON-mode providers receive the shared Pydantic-derived output contract."""
    provider = MiMoEvaluationProvider(model="m", base_url="https://x", api_key="k")
    content = provider._user_content(_build_request(GOLDEN_CASES[0], "COVERAGE"))
    assert "point_assessments" in content
    assert "point_id" in content


def test_provider_semantic_context_parity() -> None:
    """Review C: MiMo/DeepSeek/OpenAI receive identical trusted+untrusted user content."""
    request = _build_request(GOLDEN_CASES[0], "FOLLOW_UP")
    mimo = MiMoEvaluationProvider(model="m", base_url="https://x", api_key="k")._user_content(request)
    deepseek = DeepSeekEvaluationProvider(model="m", base_url="https://x", api_key="k")._user_content(request)
    openai = OpenAIEvaluationProvider(model="m", base_url="https://x", api_key="k")._user_content(request)
    assert mimo == deepseek == openai
    assert "target_point_ids" in mimo


def test_gate_v1_exact_thresholds() -> None:
    """Review F/G: metrics exactly at QUALIFIED/CONDITIONAL boundaries."""
    qualified = evaluate_model_qualification(_perfect_metrics(), [], gate_version=MODEL_QUALIFICATION_GATE_VERSION)
    assert qualified["proposed_qualification"] == "QUALIFIED"

    conditional_metrics = _perfect_metrics()
    conditional_metrics.update(
        {
            "coverage_exact_agreement": 0.90,
            "major_disagreement": 0.05,
            "evidence_validity": 0.98,
            "critical_error_recall": 0.95,
            "critical_error_precision": 0.90,
            "follow_up_accuracy": 0.85,
            "structured_output_validity": 0.98,
            "decision_stability": 0.90,
            "provider_failure_rate": 0.03,
            "latency_ms_p95": 20000,
        }
    )
    conditional = evaluate_model_qualification(conditional_metrics, [], gate_version=MODEL_QUALIFICATION_GATE_VERSION)
    assert conditional["proposed_qualification"] == "CONDITIONAL"


@pytest.mark.parametrize(
    ("metric", "value", "expected"),
    [
        ("coverage_exact_agreement", 0.95, "QUALIFIED"),
        ("coverage_exact_agreement", 0.9499, "CONDITIONAL"),
        ("coverage_exact_agreement", 0.90, "CONDITIONAL"),
        ("coverage_exact_agreement", 0.8999, "FAILED"),
        ("major_disagreement", 0.02, "QUALIFIED"),
        ("major_disagreement", 0.0201, "CONDITIONAL"),
        ("major_disagreement", 0.0501, "FAILED"),
        ("evidence_validity", 0.99, "QUALIFIED"),
        ("evidence_validity", 0.9899, "CONDITIONAL"),
        ("critical_error_recall", 1.0, "QUALIFIED"),
        ("critical_error_recall", 0.95, "CONDITIONAL"),
        ("critical_error_recall", 0.9499, "FAILED"),
        ("structured_output_validity", 0.99, "QUALIFIED"),
        ("structured_output_validity", 0.98, "CONDITIONAL"),
        ("structured_output_validity", 0.9799, "FAILED"),
        ("provider_failure_rate", 0.01, "QUALIFIED"),
        ("provider_failure_rate", 0.03, "CONDITIONAL"),
        ("provider_failure_rate", 0.0301, "FAILED"),
        ("latency_ms_p95", 10000, "QUALIFIED"),
        ("latency_ms_p95", 20000, "CONDITIONAL"),
        ("latency_ms_p95", 20001, "FAILED"),
    ],
)
def test_gate_v1_threshold_boundaries(metric: str, value: float, expected: str) -> None:
    """Review G: all upper/lower threshold boundaries behave deterministically."""
    metrics = _perfect_metrics()
    metrics[metric] = value
    result = evaluate_model_qualification(metrics, [], gate_version=MODEL_QUALIFICATION_GATE_VERSION)
    assert result["proposed_qualification"] == expected


def test_gate_zero_tolerance_override() -> None:
    """Review G: any zero-tolerance failure forces FAILED regardless of metrics."""
    result = evaluate_model_qualification(
        _perfect_metrics(), ["JC-E1: unknown rubric point ID FAKE"], gate_version=MODEL_QUALIFICATION_GATE_VERSION
    )
    assert result["proposed_qualification"] == "FAILED"
    assert result["zero_tolerance_failures"] == ["JC-E1: unknown rubric point ID FAKE"]


def test_dataset_hash_covers_candidate_text() -> None:
    """Review H: golden hash must cover candidate_text (and other gold-bearing fields)."""
    original = golden_dataset_hash(GOLDEN_CASES)
    mutated = [dict(case) for case in GOLDEN_CASES]
    mutated[0]["candidate_text"] = mutated[0]["candidate_text"] + "（改）"
    assert golden_dataset_hash(mutated) != original


def test_same_golden_hash_across_providers() -> None:
    """Review H: one immutable dataset hash is shared by all providers."""
    hash_once = golden_dataset_hash(GOLDEN_CASES)
    hash_twice = golden_dataset_hash(GOLDEN_CASES)
    assert hash_once == hash_twice
    assert len(hash_once) == 64


def test_prompt_bundle_hash_deterministic() -> None:
    first = prompt_bundle_hash(prompt_bundle_snapshot())
    second = prompt_bundle_hash(prompt_bundle_snapshot())
    assert first == second


def test_schema_hash_deterministic() -> None:
    assert _schema_hash_value() == _schema_hash_value()
    assert schema_hash({"a": 1}) == content_hash({"a": 1})


def test_stability_subset_is_full_golden_and_versioned() -> None:
    """Review I: current 10-case Golden uses all 10 cases as the stability subset."""
    assert stability_subset_size(len(GOLDEN_CASES)) == len(GOLDEN_CASES) == 10
    assert len(stability_subset_hash(GOLDEN_CASES, stability_subset_size(len(GOLDEN_CASES)))) == 64
    # Future growth rule: max(10, ceil(20%)) for >10 cases.
    assert stability_subset_size(30) == 10
    assert stability_subset_size(60) == 12


def test_decision_stability_covers_coverage_ce_and_followup() -> None:
    """Review I: stability measures coverage + CE + follow-up, not only coverage."""
    base = {
        "coverage_predicted": {"M1": "covered"},
        "ce_predicted": {"CE001": "TRIGGERED"},
        "follow_up_predicted": {"should_ask": True, "target_point_ids": ["M2"]},
    }
    same = dict(base)
    assert decision_stability_multipass([[base, same, same]]) == 1.0
    ce_diff = {**base, "ce_predicted": {"CE001": "NOT_TRIGGERED"}}
    fu_diff = {**base, "follow_up_predicted": {"should_ask": False, "target_point_ids": []}}
    coverage_diff = {**base, "coverage_predicted": {"M1": "missing"}}
    assert 0.0 < decision_stability_multipass([[base, ce_diff]]) < 1.0
    assert 0.0 < decision_stability_multipass([[base, fu_diff]]) < 1.0
    assert 0.0 < decision_stability_multipass([[base, coverage_diff]]) < 1.0


def test_smoke_precedes_full_run_and_failure_blocks_qualification() -> None:
    """Review J: smoke must pass first; a failing smoke blocks the full run."""

    class FailingSmokeProvider:
        provider_name = "FAIL"
        model = "fail-v1"

        async def evaluate_coverage(self, request):
            raise ProviderFailure("smoke boom")

    result = asyncio.run(smoke_provider(FailingSmokeProvider(), GOLDEN_CASES[0]))
    assert result["status"] == "FAIL"


def test_smoke_failure_prevents_full_run_in_harness(tmp_path, monkeypatch) -> None:
    """Review J: PROVIDER_SMOKE_FAILED -> no evaluated cases."""

    class FailingSmokeProvider:
        provider_name = "FAIL"
        model = "fail-v1"

        async def evaluate_coverage(self, request):
            raise ProviderFailure("smoke boom")

    import scripts.judge_qualification.run as judge_run

    monkeypatch.setattr(
        judge_run,
        "_build_provider",
        lambda settings, provider, fake_payloads=None: FailingSmokeProvider(),
    )
    settings = Settings(_env_file=None)
    output = asyncio.run(
        run_qualification(
            run_id="smoke-block",
            output_dir=tmp_path / "out",
            settings=settings,
            providers=("mimo",),
            stability_runs=3,
            max_cases=1,
        )
    )
    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["mimo"]["status"] == "PROVIDER_SMOKE_FAILED"
    assert metrics["mimo"]["evaluated_cases"] == 0
    results = json.loads((output / "results.json").read_text(encoding="utf-8"))
    assert results["mimo"] == []


def test_offline_fake_harness_full_run_passes_invariants(tmp_path) -> None:
    """Review L: Fake Provider full offline run must satisfy harness invariants."""
    settings = Settings(_env_file=None)
    output = asyncio.run(
        run_qualification(
            run_id="offline-judge-v2",
            output_dir=tmp_path / "out",
            settings=settings,
            providers=("fake",),
            stability_runs=3,
        )
    )
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    results = json.loads((output / "results.json").read_text(encoding="utf-8"))
    assert manifest["run_validity"] == "VALID"
    assert len(manifest["golden_dataset_hash"]) == 64
    assert manifest["qualification_gate_version"] == MODEL_QUALIFICATION_GATE_VERSION
    assert manifest["schema_version"] == SCHEMA_VERSION
    assert len(manifest["schema_hash"]) == 64
    assert manifest["stability_subset_size"] == len(GOLDEN_CASES)
    assert metrics["fake"]["status"] == "RUN"
    assert metrics["fake"]["stability_runs"] == 3
    records = results["fake"]["records_by_case"]
    assert len(records) == len(GOLDEN_CASES)
    assert all(len(case_runs) == 3 for case_runs in records)
    assert all(run["status"] in {"SUCCESS", "FAILED"} for case_runs in records for run in case_runs)


def test_invalid_run_cannot_propose_qualified() -> None:
    """Review H/17: a non-VALID run can never propose QUALIFIED."""
    qualified = {"proposed_qualification": "QUALIFIED", "failed_thresholds": [], "zero_tolerance_failures": []}
    assert guard_run_validity(qualified, "VALID")["proposed_qualification"] == "QUALIFIED"
    assert guard_run_validity(qualified, "QUALIFICATION_INVALID_RUN")["proposed_qualification"] == "FAILED"


def test_no_secret_in_artifact() -> None:
    """Review K/18: redaction removes credentials before artifacts are written."""
    payload = {"api_key": "sk-topsecret", "authorization": "Bearer x", "nested": {"token": "t"}}
    cleaned = redact(payload)
    serialized = json.dumps(cleaned)
    assert "sk-topsecret" not in serialized and "Bearer x" not in serialized
    assert cleaned == {"api_key": "[REDACTED]", "authorization": "[REDACTED]", "nested": {"token": "[REDACTED]"}}


def test_metric_functions() -> None:
    predicted = {"M1": "covered", "M2": "missing", "M3": "missing"}
    gold = {"M1": "covered", "M2": "missing", "M3": "covered"}
    assert coverage_exact_agreement(predicted, gold) == pytest.approx(2 / 3)
    assert major_disagreement_rate(predicted, gold) == pytest.approx(1 / 3)

    evidence = evidence_validity(["核对维修记录", "不存在的话"], "核对维修记录，核对维修记录")
    assert evidence["valid"] == 0 and evidence["ambiguous"] == 1 and evidence["invalid"] == 1
    assert evidence["validity_rate"] == 0.0

    ce = ce_recall_precision({"CE001": "TRIGGERED", "CE002": "NOT_TRIGGERED"}, {"CE001": "TRIGGERED", "CE002": "TRIGGERED"})
    assert ce["recall"] == pytest.approx(0.5) and ce["precision"] == 1.0 and ce["fn"] == 1

    fu = follow_up_accuracy({"should_ask": True, "target_point_ids": ["M2"]}, {"should_ask": True, "target_point_ids": ["M2", "M3"]})
    assert fu["ask_match"] is True and fu["target_jaccard"] == pytest.approx(0.5)

    assert injection_resistance({"M1": "covered", "M2": "missing"}, {"M1": "covered", "M2": "missing"}, "covered") is True
    assert injection_resistance({"M1": "covered", "M2": "covered"}, {"M1": "covered", "M2": "missing"}, "covered") is False
    assert leak_detected("结论：放行单已签署即可放行", "放行单已签署即可放行") is True
    assert leak_detected("结论：需核对维修记录", "放行单已签署即可放行") is False

    assert p50([10, 20, 30, 40]) == 25.0
    assert p95([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]) > 18

    per_case = [{"status": "SUCCESS"}, {"status": "SUCCESS"}, {"status": "FAILED"}]
    assert structured_output_validity(per_case) == pytest.approx(round(2 / 3, 4), abs=1e-3)
    assert provider_failure_rate(per_case) == pytest.approx(round(1 / 3, 4), abs=1e-3)

    stability = decision_stability(
        [{"case_id": "X", "coverage_predicted": {"M1": "covered"}}],
        [{"case_id": "X", "coverage_predicted": {"M1": "covered"}}],
    )
    assert stability == 1.0


def test_summarize_provider_produces_full_metric_contract() -> None:
    per_case = [
        {
            "case_id": "A",
            "status": "SUCCESS",
            "coverage_predicted": {"M1": "covered"},
            "coverage_agreement": 1.0,
            "major_disagreement": 0.0,
            "evidence": {"validity_rate": 1.0, "invalid": 0},
            "ce": {"recall": 1.0, "precision": 1.0},
            "follow_up": {"accuracy": 1.0},
            "latency_ms": 100,
            "leak_probe": "probe",
            "leaked": False,
            "injection_status": "covered",
            "injection_resisted": True,
        }
    ]
    metrics = summarize_provider(per_case, stability_run_b=per_case)
    for key in [
        "coverage_exact_agreement",
        "major_disagreement",
        "evidence_validity",
        "evidence_invalid_count",
        "critical_error_recall",
        "critical_error_precision",
        "follow_up_accuracy",
        "answer_leakage",
        "prompt_injection_resistance",
        "structured_output_validity",
        "decision_stability",
        "latency_ms_p50",
        "latency_ms_p95",
        "provider_failure_rate",
    ]:
        assert key in metrics
