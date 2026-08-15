from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from app.ai.providers.base import EvaluationRequest
from app.ai.providers.evaluation.fake import FakeEvaluationProvider
from app.ai.schemas.critical_error import CriticalErrorResponse
from app.ai.schemas.follow_up import FollowUpResponse
from app.core.security import redact
from app.db.base import Base
from app.exam.state_machine import (
    InvalidTransitionError,
    StateVersionConflictError,
    transition_attempt,
    transition_item,
)
from app.normalization.normalizer import normalize
from app.normalization.vocabulary import VocabularySnapshot
from app.repositories.core import IdempotencyConflictError, execute_idempotently
from app.scoring.critical_error import aggregate_critical_error
from app.scoring.engine import calculate_score
from app.scoring.evidence import resolve_quote
from app.services.jobs import run_fake_worker
from app.services.versioning import ImmutablePublishedVersionError, assert_version_mutable
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


class Record:
    def __init__(self, state: str, state_version: int = 0):
        self.state, self.state_version = state, state_version


def test_evidence_is_deterministic_and_ambiguous_is_not_valid() -> None:
    assert resolve_quote("按手册放行", "手册").status == "VALID"
    assert resolve_quote("手册，手册", "手册").status == "AMBIGUOUS"
    assert resolve_quote("按手册放行", "不存在").status == "INVALID"


def test_critical_error_is_sticky_until_human_override() -> None:
    assert aggregate_critical_error(["TRIGGERED", "NOT_TRIGGERED"]) == "TRIGGERED"
    assert aggregate_critical_error(["TRIGGERED"], human_override="NOT_TRIGGERED") == "OVERRIDDEN_BY_HUMAN"


def test_decimal_scoring_never_uses_float() -> None:
    score = calculate_score([{"status": "covered", "weight": Decimal("3.2"), "partial_weight": Decimal(1)}, {"status": "partial", "weight": Decimal(5), "partial_weight": Decimal("2.5")}, {"status": "uncertain", "weight": Decimal(100), "partial_weight": Decimal(100)}])
    assert score == Decimal("5.7")
    assert isinstance(score, Decimal)


def test_normalization_layers_and_low_confidence_warning() -> None:
    result = normalize("B七三七NG 的 M P D，维修放心；L 属于保留故障", VocabularySnapshot(version="v1"))
    assert "B737NG" in result.normalized_text and "MPD" in result.normalized_text and "维修放行" in result.normalized_text
    assert "L 属于" in result.normalized_text
    assert result.warnings


def test_state_machine_and_optimistic_version() -> None:
    attempt = Record("CREATED")
    transition_attempt(attempt, "READY", 0)
    assert (attempt.state, attempt.state_version) == ("READY", 1)
    with pytest.raises(StateVersionConflictError):
        transition_attempt(attempt, "IN_PROGRESS", 0)
    item = Record("PENDING")
    transition_item(item, "PRESENTING", 0)
    with pytest.raises(InvalidTransitionError):
        transition_item(item, "FINALIZED", 1)


def test_idempotency_replays_identical_request_and_rejects_changed_payload() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[])
    # Only this test's table is needed; it uses the full metadata create below for portable UUID handling.
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        first = execute_idempotently(session, "u1", "key", {"x": 1}, lambda: (201, {"id": "a"}))
        session.commit()
        second = execute_idempotently(session, "u1", "key", {"x": 1}, lambda: (201, {"id": "b"}))
        assert first[:2] == second[:2] and second[2] is True
        with pytest.raises(IdempotencyConflictError):
            execute_idempotently(session, "u1", "key", {"x": 2}, lambda: (201, {}))


def test_structured_schemas_prohibit_unproven_trigger_and_followup_shape() -> None:
    with pytest.raises(ValidationError):
        CriticalErrorResponse.model_validate({"critical_error_assessments": [{"critical_error_id": "CE1", "result": "TRIGGERED", "evidence_quotes": [], "reason": "x"}]})
    with pytest.raises(ValidationError):
        FollowUpResponse.model_validate({"should_ask": False, "target_point_ids": ["P1"], "follow_up_question": None, "reason": "x"})


def test_fake_provider_supports_a_vertical_slice_without_network() -> None:
    provider = FakeEvaluationProvider({"COVERAGE": {"point_assessments": [{"point_id": "P1", "status": "covered", "evidence_quotes": [{"quote": "按手册"}], "confidence": 1.0, "reason": "明确陈述"}]}})
    from app.ai.schemas.coverage import CoverageResponse
    response = asyncio.run(provider.evaluate_coverage(EvaluationRequest(task_type="COVERAGE", system_prompt="rules", candidate_text="按手册", rubric_snapshot={"points": ["P1"]}, output_type=CoverageResponse, prompt_version="v1")))
    assert response.value.point_assessments[0].point_id == "P1"


def test_audit_redaction_removes_credentials() -> None:
    assert redact({"Authorization": "Bearer secret", "nested": {"api_key": "nope", "safe": "yes"}}) == {"Authorization": "[REDACTED]", "nested": {"api_key": "[REDACTED]", "safe": "yes"}}


def test_published_version_cannot_be_mutated() -> None:
    record = type("PublishedRecord", (), {"status": "PUBLISHED"})()
    with pytest.raises(ImmutablePublishedVersionError):
        assert_version_mutable(record)


def test_job_failure_is_durable_and_does_not_switch_provider() -> None:
    class Job:
        def __init__(self) -> None:
            self.state = "PENDING"
            self.attempts = 0
            self.last_error = None
            self.payload = {"provider": "DEEPSEEK"}

    job = run_fake_worker(Job(), lambda _: (_ for _ in ()).throw(RuntimeError("timeout")))
    assert job.state == "FAILED" and job.attempts == 1 and job.last_error == "timeout"
    assert job.payload["provider"] == "DEEPSEEK"
