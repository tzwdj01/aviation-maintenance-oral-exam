"""Sprint 1C harness v2 reliability regression coverage.

Covers the DeepSeek JSON-mode transport contract, per-case-run checkpointing, simulated
process interruption, resume SKIP_COMPLETED semantics, frozen-input REFUSE_RESUME guards,
deterministic reassembly from checkpoints, no duplicate case-runs after resume, and
no-secret checkpoints/artifacts.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from app.ai.providers.base import ProviderFailure
from app.ai.providers.evaluation.deepseek import DeepSeekEvaluationProvider
from app.ai.schemas.coverage import CoverageResponse
from app.core.config import Settings
from pydantic import ValidationError
from scripts.judge_qualification.golden import GOLDEN_CASES
from scripts.judge_qualification.prompts import (
    JSON_MODE_TRANSPORT_INSTRUCTION,
    PROMPT_BUNDLE_VERSION,
    prompt_bundle_snapshot,
    system_prompt_for,
)
from scripts.judge_qualification.run import (
    JUDGE_QUALIFICATION_HARNESS_VERSION,
    QualificationResumeMismatch,
    _atomic_write_json,
    _build_request,
    _case_checkpoint_path,
    _checkpoint_root,
    _load_checkpoint,
    _smoke_checkpoint_path,
    run_qualification,
)

TASKS = ("COVERAGE", "CRITICAL_ERROR", "QUALITY_RISK", "FOLLOW_UP", "FINAL_ASSESSMENT")


def _ok_record(case_id: str) -> dict:
    return {
        "case_id": case_id,
        "scenario": "test",
        "status": "SUCCESS",
        "coverage_predicted": {"M1": "covered"},
        "ce_predicted": {"CE001": "NOT_TRIGGERED"},
        "follow_up_predicted": {"should_ask": False, "target_point_ids": []},
        "final_predicted": {"initial_mastery": "ADEQUATE", "final_mastery": "ADEQUATE", "prompt_dependency": "A"},
        "coverage_agreement": 1.0,
        "major_disagreement": 0.0,
        "evidence": {"total_quotes": 0, "valid": 0, "ambiguous": 0, "invalid": 0, "validity_rate": None},
        "ce": {"tp": 0, "fn": 0, "fp": 0, "recall": None, "precision": None},
        "follow_up": {"ask_match": True, "target_jaccard": 1.0, "exact": True, "accuracy": 1.0},
        "pass_latencies_ms": {"COVERAGE": 1},
        "latency_ms": 1,
        "leak_probe": None,
        "leaked": False,
        "injection_status": None,
        "injection_resisted": None,
        "pass_status": {task: "SUCCESS" for task in TASKS},
    }


# ---------------------------------------------------------------------------
# DeepSeek JSON-mode transport contract
# ---------------------------------------------------------------------------


def test_deepseek_prompt_contains_literal_json_contract() -> None:
    """DeepSeek's response_format json_object requires the literal word 'json' in the prompt."""
    for task in TASKS:
        prompt = system_prompt_for(task)
        assert "json" in prompt.lower()
        assert prompt.endswith(JSON_MODE_TRANSPORT_INSTRUCTION)
        assert "Return JSON only." in prompt
        assert "Do not output Markdown, prose, code fences, or extra fields" in prompt


def test_transport_instruction_is_neutral_and_identical_across_passes() -> None:
    """The JSON transport suffix is the same for every pass: no scoring hint per task."""
    suffixes = {system_prompt_for(task)[-len(JSON_MODE_TRANSPORT_INSTRUCTION):] for task in TASKS}
    assert suffixes == {JSON_MODE_TRANSPORT_INSTRUCTION}


def test_transport_fix_does_not_change_prompt_business_semantics() -> None:
    """Prompt Bundle bump is transport-only: business pass prompts are unchanged."""
    assert PROMPT_BUNDLE_VERSION == "prompt-bundle-v2"
    snapshot = prompt_bundle_snapshot()
    assert snapshot["json_mode_transport_instruction"] == JSON_MODE_TRANSPORT_INSTRUCTION
    assert snapshot["rendered_prompts"] == {task: system_prompt_for(task) for task in snapshot["pass_prompts"]}
    # Hash is deterministic and reflects the actual rendered prompt content.
    assert json.dumps(snapshot, ensure_ascii=False, sort_keys=True) == json.dumps(
        prompt_bundle_snapshot(), ensure_ascii=False, sort_keys=True
    )


def test_output_schema_still_derived_from_pydantic_and_extra_forbidden() -> None:
    """Schema stays eval-schema-v1 derived from the shared Pydantic models; extra fields forbid."""
    from scripts.judge_qualification.run import OUTPUT_TYPES

    assert OUTPUT_TYPES["COVERAGE"].model_json_schema() == CoverageResponse.model_json_schema()
    assert CoverageResponse.model_config.get("extra") == "forbid"
    CoverageResponse.model_validate({"point_assessments": []})
    with pytest.raises(ValidationError):
        CoverageResponse.model_validate({"point_assessments": [], "points": []})


def test_candidate_answer_stays_in_untrusted_boundary_with_transport_fix() -> None:
    provider = DeepSeekEvaluationProvider(model="m", base_url="https://x", api_key="k")
    case = GOLDEN_CASES[0]
    content = provider._user_content(_build_request(case, "COVERAGE"))
    trusted_part, untrusted_part = content.split("UNTRUSTED_CANDIDATE_DATA:")
    assert "TRUSTED_EVALUATION_CONTEXT:" in trusted_part
    assert case["candidate_text"] in untrusted_part
    assert "M1" in trusted_part
    assert "M1" not in untrusted_part
    # Transport instruction lives in the system prompt (not in either user-content boundary).
    assert JSON_MODE_TRANSPORT_INSTRUCTION not in content


def test_deepseek_strict_schema_parsing_still_enforced() -> None:
    provider = DeepSeekEvaluationProvider(model="m", base_url="https://x", api_key="k")
    request = _build_request(GOLDEN_CASES[0], "COVERAGE")
    with pytest.raises(ProviderFailure, match="Structured response failed validation"):
        provider._parse(json.dumps({"point_assessments": [], "points": []}), request, {}, None)
    parsed = provider._parse(
        json.dumps(
            {
                "point_assessments": [
                    {
                        "point_id": "M1",
                        "status": "covered",
                        "evidence_quotes": [{"quote": "核对维修记录已由授权人员签署"}],
                        "confidence": 1.0,
                        "reason": "明确陈述",
                    }
                ]
            }
        ),
        request,
        {},
        None,
    )
    assert isinstance(parsed.value, CoverageResponse)


# ---------------------------------------------------------------------------
# Checkpoint / resume invariants
# ---------------------------------------------------------------------------


def test_checkpoint_written_after_every_case_run(tmp_path) -> None:
    settings = Settings(_env_file=None)
    output = asyncio.run(
        run_qualification(
            run_id="cp-every",
            output_dir=tmp_path / "out",
            settings=settings,
            providers=("fake",),
            stability_runs=3,
            max_cases=2,
        )
    )
    root = _checkpoint_root(tmp_path / "out", "cp-every")
    run_files = sorted((root / "fake").rglob("run-*.json"))
    assert len(run_files) == 6  # 2 cases x 3 runs
    for path in run_files:
        checkpoint = _load_checkpoint(path)
        assert checkpoint["provider"] == "fake"
        assert checkpoint["model"] == "fake-evaluation-v1"
        assert checkpoint["record"]["status"] == "SUCCESS"
        assert checkpoint["frozen_inputs"]["harness_version"] == JUDGE_QUALIFICATION_HARNESS_VERSION
        assert checkpoint["frozen_inputs"]["golden_dataset_version"] == "judge-qual-golden-v1"
    smoke = _load_checkpoint(_smoke_checkpoint_path(root / "fake"))
    assert smoke["smoke"]["status"] == "PASS"
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_status"] == "COMPLETED"
    assert manifest["harness_version"] == JUDGE_QUALIFICATION_HARNESS_VERSION


def test_resume_after_interruption_skips_completed_and_reruns_incomplete(tmp_path, monkeypatch) -> None:
    import scripts.judge_qualification.run as judge_run

    settings = Settings(_env_file=None)
    run_id = "resume-interrupt"
    output_dir = tmp_path / "out"
    calls: list[str] = []

    def make_runner(limit: int):
        async def runner(provider, case):
            calls.append(case["case_id"])
            if len(calls) > limit:
                raise RuntimeError("simulated interruption")
            return _ok_record(case["case_id"])

        return runner

    monkeypatch.setattr(judge_run, "_run_case_once", make_runner(3))
    with pytest.raises(RuntimeError, match="simulated interruption"):
        asyncio.run(
            judge_run.run_qualification(
                run_id=run_id,
                output_dir=output_dir,
                settings=settings,
                providers=("fake",),
                stability_runs=2,
                max_cases=2,
            )
        )
    # 3 case-runs completed and persisted before the interruption; the 4th raised.
    assert calls == ["JC-A1", "JC-A1", "JC-A2", "JC-A2"]
    root = _checkpoint_root(output_dir, run_id)
    run_files = sorted((root / "fake").rglob("run-*.json"))
    assert len(run_files) == 3
    assert not _case_checkpoint_path(root / "fake", "JC-A2", 2).exists()

    # Resume: only the incomplete case-run (JC-A2 run 2) is re-executed.
    calls.clear()
    monkeypatch.setattr(judge_run, "_run_case_once", make_runner(10**9))
    output = asyncio.run(
        judge_run.run_qualification(
            run_id=run_id,
            output_dir=output_dir,
            settings=settings,
            providers=("fake",),
            stability_runs=2,
            max_cases=2,
            resume=True,
        )
    )
    assert calls == ["JC-A2"]  # no duplicate case-runs after resume
    results = json.loads((output / "results.json").read_text(encoding="utf-8"))
    records = results["fake"]["records_by_case"]
    assert len(records) == 2
    assert all(len(case_runs) == 2 for case_runs in records)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_status"] == "COMPLETED"
    assert manifest["run_validity"] == "VALID"


def test_smoke_persisted_and_reused_on_resume(tmp_path, monkeypatch) -> None:
    import scripts.judge_qualification.run as judge_run

    settings = Settings(_env_file=None)
    run_id = "smoke-reuse"
    output_dir = tmp_path / "out"
    smoke_calls: list[int] = []
    original_smoke = judge_run.smoke_provider

    async def counting_smoke(provider, case):
        smoke_calls.append(1)
        return await original_smoke(provider, case)

    async def runner(provider, case):
        return _ok_record(case["case_id"])

    monkeypatch.setattr(judge_run, "smoke_provider", counting_smoke)
    monkeypatch.setattr(judge_run, "_run_case_once", runner)
    asyncio.run(
        judge_run.run_qualification(
            run_id=run_id,
            output_dir=output_dir,
            settings=settings,
            providers=("fake",),
            stability_runs=1,
            max_cases=1,
        )
    )
    assert len(smoke_calls) == 1
    asyncio.run(
        judge_run.run_qualification(
            run_id=run_id,
            output_dir=output_dir,
            settings=settings,
            providers=("fake",),
            stability_runs=1,
            max_cases=1,
            resume=True,
        )
    )
    assert len(smoke_calls) == 1  # persisted PASS reused; no new provider call


def test_fresh_run_refuses_existing_checkpoints(tmp_path, monkeypatch) -> None:
    import scripts.judge_qualification.run as judge_run

    settings = Settings(_env_file=None)
    run_id = "no-mix"
    output_dir = tmp_path / "out"

    async def runner(provider, case):
        return _ok_record(case["case_id"])

    monkeypatch.setattr(judge_run, "_run_case_once", runner)
    asyncio.run(
        judge_run.run_qualification(
            run_id=run_id,
            output_dir=output_dir,
            settings=settings,
            providers=("fake",),
            stability_runs=1,
            max_cases=1,
        )
    )
    with pytest.raises(RuntimeError, match="checkpoints already exist"):
        asyncio.run(
            judge_run.run_qualification(
                run_id=run_id,
                output_dir=output_dir,
                settings=settings,
                providers=("fake",),
                stability_runs=1,
                max_cases=1,
            )
        )


@pytest.mark.parametrize(
    ("field", "new_value"),
    [
        ("golden_dataset_version", "judge-qual-golden-v9"),
        ("golden_dataset_hash", "0" * 64),
        ("prompt_bundle_version", "prompt-bundle-v9"),
        ("prompt_bundle_hash", "1" * 64),
        ("schema_version", "eval-schema-v9"),
        ("schema_hash", "2" * 64),
        ("qualification_gate_version", "v2"),
        ("stability_subset_hash", "3" * 64),
        ("harness_version", "judge-harness-v9"),
    ],
)
def test_resume_refuses_frozen_input_mismatch(tmp_path, monkeypatch, field: str, new_value: str) -> None:
    import scripts.judge_qualification.run as judge_run

    settings = Settings(_env_file=None)
    run_id = f"refuse-{field}"
    output_dir = tmp_path / "out"

    async def runner(provider, case):
        return _ok_record(case["case_id"])

    monkeypatch.setattr(judge_run, "_run_case_once", runner)
    asyncio.run(
        judge_run.run_qualification(
            run_id=run_id,
            output_dir=output_dir,
            settings=settings,
            providers=("fake",),
            stability_runs=1,
            max_cases=1,
        )
    )
    root = _checkpoint_root(output_dir, run_id)
    run_files = list((root / "fake").rglob("run-*.json"))
    assert len(run_files) == 1
    checkpoint = _load_checkpoint(run_files[0])
    checkpoint["frozen_inputs"][field] = new_value
    _atomic_write_json(run_files[0], checkpoint)

    with pytest.raises(QualificationResumeMismatch) as excinfo:
        asyncio.run(
            judge_run.run_qualification(
                run_id=run_id,
                output_dir=output_dir,
                settings=settings,
                providers=("fake",),
                stability_runs=1,
                max_cases=1,
                resume=True,
            )
        )
    assert excinfo.value.code == "QUALIFICATION_RESUME_MISMATCH"
    assert field in str(excinfo.value)


def test_resume_refuses_model_mismatch(tmp_path, monkeypatch) -> None:
    import scripts.judge_qualification.run as judge_run

    settings = Settings(_env_file=None)
    run_id = "refuse-model"
    output_dir = tmp_path / "out"

    async def runner(provider, case):
        return _ok_record(case["case_id"])

    monkeypatch.setattr(judge_run, "_run_case_once", runner)
    asyncio.run(
        judge_run.run_qualification(
            run_id=run_id,
            output_dir=output_dir,
            settings=settings,
            providers=("fake",),
            stability_runs=1,
            max_cases=1,
        )
    )
    root = _checkpoint_root(output_dir, run_id)
    run_files = list((root / "fake").rglob("run-*.json"))
    checkpoint = _load_checkpoint(run_files[0])
    checkpoint["model"] = "wrong-model"
    _atomic_write_json(run_files[0], checkpoint)

    with pytest.raises(QualificationResumeMismatch, match="model"):
        asyncio.run(
            judge_run.run_qualification(
                run_id=run_id,
                output_dir=output_dir,
                settings=settings,
                providers=("fake",),
                stability_runs=1,
                max_cases=1,
                resume=True,
            )
        )


def test_resume_refuses_provider_mismatch(tmp_path, monkeypatch) -> None:
    import scripts.judge_qualification.run as judge_run

    settings = Settings(_env_file=None)
    run_id = "refuse-provider"
    output_dir = tmp_path / "out"

    async def runner(provider, case):
        return _ok_record(case["case_id"])

    monkeypatch.setattr(judge_run, "_run_case_once", runner)
    asyncio.run(
        judge_run.run_qualification(
            run_id=run_id,
            output_dir=output_dir,
            settings=settings,
            providers=("fake",),
            stability_runs=1,
            max_cases=1,
        )
    )
    root = _checkpoint_root(output_dir, run_id)
    run_files = list((root / "fake").rglob("run-*.json"))
    checkpoint = _load_checkpoint(run_files[0])
    checkpoint["provider"] = "deepseek"
    _atomic_write_json(run_files[0], checkpoint)

    with pytest.raises(QualificationResumeMismatch, match="provider"):
        asyncio.run(
            judge_run.run_qualification(
                run_id=run_id,
                output_dir=output_dir,
                settings=settings,
                providers=("fake",),
                stability_runs=1,
                max_cases=1,
                resume=True,
            )
        )


def test_reassemble_rebuilds_identically_from_checkpoints(tmp_path, monkeypatch) -> None:
    import scripts.judge_qualification.run as judge_run

    settings = Settings(_env_file=None)
    run_id = "reassemble"
    output_dir = tmp_path / "out"
    calls: list[str] = []

    async def runner(provider, case):
        calls.append(case["case_id"])
        return _ok_record(case["case_id"])

    monkeypatch.setattr(judge_run, "_run_case_once", runner)
    output = asyncio.run(
        judge_run.run_qualification(
            run_id=run_id,
            output_dir=output_dir,
            settings=settings,
            providers=("fake",),
            stability_runs=3,
            max_cases=2,
        )
    )
    first_metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    first_results = json.loads((output / "results.json").read_text(encoding="utf-8"))

    calls.clear()
    output2 = judge_run.reassemble_run(
        run_id=run_id,
        output_dir=output_dir,
        settings=settings,
        providers=("fake",),
        stability_runs=3,
        max_cases=2,
    )
    assert calls == []  # reassembly makes zero provider calls
    second_metrics = json.loads((output2 / "metrics.json").read_text(encoding="utf-8"))
    second_results = json.loads((output2 / "results.json").read_text(encoding="utf-8"))
    assert second_metrics == first_metrics
    assert second_results == first_results
    manifest = json.loads((output2 / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_status"] == "COMPLETED"
    assert manifest["run_validity"] == "VALID"


def test_secrets_absent_from_checkpoints_and_artifacts(tmp_path, monkeypatch) -> None:
    import scripts.judge_qualification.run as judge_run

    settings = Settings(_env_file=None)
    run_id = "no-secret-cp"
    output_dir = tmp_path / "out"

    async def runner(provider, case):
        record = _ok_record(case["case_id"])
        record["status"] = "FAILED"
        record["failed_pass"] = "COVERAGE"
        record["error"] = "provider http error 400 sk-super-secret-value Bearer tok-1234567890"
        record["api_key"] = "sk-abcdef1234567890"
        return record

    monkeypatch.setattr(judge_run, "_run_case_once", runner)
    output = asyncio.run(
        judge_run.run_qualification(
            run_id=run_id,
            output_dir=output_dir,
            settings=settings,
            providers=("fake",),
            stability_runs=1,
            max_cases=1,
        )
    )
    for path in (output / "checkpoints").rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "sk-super-secret-value" not in text
        assert "sk-abcdef1234567890" not in text
        assert "tok-1234567890" not in text
    # The case-run checkpoint carrying the failed record must show the redaction marker.
    case_run_files = list((output / "checkpoints").rglob("run-*.json"))
    assert len(case_run_files) == 1
    assert "[REDACTED]" in case_run_files[0].read_text(encoding="utf-8")
    for name in ("results.json", "metrics.json", "failures.json"):
        text = (output / name).read_text(encoding="utf-8")
        assert "sk-super-secret-value" not in text
        assert "sk-abcdef1234567890" not in text
        assert "tok-1234567890" not in text
