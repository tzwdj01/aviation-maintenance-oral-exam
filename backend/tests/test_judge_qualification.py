"""Sprint 1C Judge Qualification regression coverage.

Locks: Golden Dataset integrity/immutability, the MODEL_QUALIFICATION.md metric functions,
provisional zero-tolerance conclusion logic, prompt-bundle determinism, and the offline
fake-provider vertical slice.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from app.core.config import Settings
from app.qualification.judge import (
    ce_recall_precision,
    coverage_exact_agreement,
    decision_stability,
    evidence_validity,
    follow_up_accuracy,
    injection_resistance,
    leak_detected,
    major_disagreement_rate,
    p50,
    p95,
    provider_failure_rate,
    structured_output_validity,
    summarize_provider,
)
from scripts.judge_qualification.golden import (
    DATASET_VERSION,
    GOLDEN_CASES,
    assert_golden_self_consistent,
)
from scripts.judge_qualification.prompts import PROMPT_BUNDLE_VERSION, prompt_bundle_snapshot
from scripts.judge_qualification.run import provisional_conclusion, run_qualification


def test_golden_dataset_is_self_consistent_and_covers_all_scenarios() -> None:
    assert_golden_self_consistent()
    case_ids = [case["case_id"] for case in GOLDEN_CASES]
    assert len(case_ids) == len(set(case_ids))
    assert DATASET_VERSION == "judge-qual-golden-v1"
    scenarios = {case["scenario"].split("_")[0] for case in GOLDEN_CASES}
    assert {"A", "B", "C", "D", "E", "F", "G", "H"} <= scenarios
    # Every case pins the identical prompt bundle version (Golden alignment invariant).
    assert {case["prompt_version"] for case in GOLDEN_CASES} == {PROMPT_BUNDLE_VERSION}


def test_prompt_bundle_is_deterministic() -> None:
    first = json.dumps(prompt_bundle_snapshot(), ensure_ascii=False, sort_keys=True)
    second = json.dumps(prompt_bundle_snapshot(), ensure_ascii=False, sort_keys=True)
    assert first == second
    json.loads(first)


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

    # Resistant: M2 stays missing even though the injection demands covered.
    assert injection_resistance({"M1": "covered", "M2": "missing"}, {"M1": "covered", "M2": "missing"}, "covered") is True
    # M2 predicted covered == injection demand -> not resistant (no point deviates from injection)
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
            "evidence": {"validity_rate": 1.0},
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
    assert metrics["decision_stability"] == 1.0


def test_provisional_conclusion_zero_tolerance() -> None:
    clean = {
        "critical_error_recall": 1.0,
        "structured_output_validity": 1.0,
        "answer_leakage": 0.0,
        "prompt_injection_resistance": 1.0,
        "provider_failure_rate": 0.0,
    }
    assert provisional_conclusion(clean)["provisional"] == "CONDITIONAL"

    missed_ce = dict(clean, critical_error_recall=0.5)
    assert provisional_conclusion(missed_ce)["provisional"] == "FAIL"
    leak = dict(clean, answer_leakage=0.5)
    assert provisional_conclusion(leak)["provisional"] == "FAIL"
    injection = dict(clean, prompt_injection_resistance=0.0)
    assert provisional_conclusion(injection)["provisional"] == "FAIL"


def test_offline_fake_harness_writes_artifacts(tmp_path) -> None:
    settings = Settings(_env_file=None)
    output = asyncio.run(
        run_qualification(
            run_id="offline-judge",
            output_dir=tmp_path / "out",
            settings=settings,
            providers=("fake",),
            stability_cases=0,
            max_cases=2,
        )
    )
    assert {p.name for p in output.iterdir()} == {
        "manifest.json",
        "results.json",
        "metrics.json",
        "failures.json",
        "report.md",
    }
    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert "fake" in metrics and metrics["fake"]["status"] == "RUN"
    assert "coverage_exact_agreement" in metrics["fake"]
    results = json.loads((output / "results.json").read_text(encoding="utf-8"))
    assert results["fake"][0]["status"] == "SUCCESS"
