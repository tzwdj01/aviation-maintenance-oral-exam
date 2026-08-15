"""Sprint 1A governance-gate coverage.

These tests lock the conformance guarantees required by GOAL.md, the accepted ADRs and
docs/TESTING.md: snapshot locking, no silent provider failover, evidence-gated credit,
raw ASR preservation, single-adopted-transcript invariant, unknown rule-ID rejection,
and governed LLM qualification.
"""

from __future__ import annotations

import uuid

import pytest
from app.ai.providers.evaluation.fake import FakeEvaluationProvider
from app.ai.providers.registry import ProviderRegistry
from app.ai.providers.speech.fake import FakeSpeechProvider
from app.ai.schemas.coverage import CoverageResponse
from app.ai.schemas.quality_risk import QualityRiskResponse
from app.db.base import Base
from app.db.session import get_db
from app.exam.assembly import lock_attempt_snapshot
from app.main import app
from app.models.domain import Answer, ASRTranscript
from app.normalization.normalizer import normalize
from app.normalization.vocabulary import VocabularySnapshot
from app.repositories.core import adopt_transcript
from app.schemas.llm_profiles import LLMProfileCreate
from app.scoring.validation import (
    UnknownRuleIdError,
    validate_known_critical_error_ids,
    validate_known_point_ids,
)
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def test_attempt_snapshot_locks_profile_plan_and_prompt() -> None:
    """ADR-0007: an attempt locks plan/profile/prompt bundle at creation; later
    default-model changes must not affect the active/historical attempt."""
    plan = {"sections": [1, 2]}
    profile = {
        "provider": "DEEPSEEK",
        "model": "deepseek-v4-pro",
        "qualification_status": "UNTESTED",
        "config": {"n": 1},
    }
    prompt_bundle = {"coverage": "v1"}
    snapshot = lock_attempt_snapshot(plan, profile, prompt_bundle)

    # Admin later changes the system default profile.
    profile["model"] = "another-model"
    profile["qualification_status"] = "QUALIFIED"
    profile["config"]["n"] = 999
    plan["sections"].append(3)
    prompt_bundle["coverage"] = "v2"

    assert snapshot["llm_profile_snapshot"] == {
        "provider": "DEEPSEEK",
        "model": "deepseek-v4-pro",
        "qualification_status": "UNTESTED",
        "config": {"n": 1},
    }
    assert snapshot["plan_snapshot"]["sections"] == [1, 2]
    assert snapshot["prompt_bundle_snapshot"] == {"coverage": "v1"}


def test_registry_is_explicit_and_never_falls_back_to_another_provider() -> None:
    """ADR-0003/0005: registry lookup is explicit; unknown providers fail, no silent failover."""
    registry = ProviderRegistry()
    registry.register_evaluation("DEEPSEEK", FakeEvaluationProvider())
    registry.register_speech("FAKE", FakeSpeechProvider())

    assert registry.evaluation("deepseek") is not None
    with pytest.raises(KeyError):
        registry.evaluation("OPENAI")
    assert registry.speech("FAKE") is not None
    with pytest.raises(KeyError):
        registry.speech("MIMO")


def test_credit_bearing_statuses_require_evidence() -> None:
    """ADR-0006/SCORING: covered/partial must carry an evidence quote; missing/uncertain may not."""
    with pytest.raises(ValidationError):
        CoverageResponse.model_validate(
            {
                "point_assessments": [
                    {"point_id": "M1", "status": "covered", "evidence_quotes": [], "reason": "x"}
                ]
            }
        )
    with pytest.raises(ValidationError):
        QualityRiskResponse.model_validate(
            {
                "quality_risk_assessments": [
                    {"point_id": "I1", "status": "partial", "evidence_quotes": [], "reason": "x"}
                ]
            }
        )
    # Non-credit statuses without evidence are allowed.
    CoverageResponse.model_validate(
        {"point_assessments": [{"point_id": "M1", "status": "missing", "evidence_quotes": [], "reason": "x"}]}
    )
    # Credit with evidence is allowed.
    CoverageResponse.model_validate(
        {
            "point_assessments": [
                {
                    "point_id": "M1",
                    "status": "covered",
                    "evidence_quotes": [{"quote": "按手册"}],
                    "reason": "x",
                }
            ]
        }
    )


def test_raw_asr_is_never_overwritten_by_normalization() -> None:
    """GOAL principle C / docs/SCORING: raw ASR is preserved; normalization is a separate view."""
    raw = "B七三七NG 维修放心"
    result = normalize(raw, VocabularySnapshot(version="v1"))
    assert raw == "B七三七NG 维修放心"
    assert result.normalized_text == "B737NG 维修放行"
    assert any(m.raw_fragment == "B七三七NG" for m in result.mappings)
    assert result.vocabulary_version == "v1"


def test_adopt_transcript_enforces_single_adopted_and_records_timestamp() -> None:
    """DATA_MODEL: at most one adopted transcript per answer; adoption records actor + time."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        answer = Answer(attempt_item_id=uuid.uuid4(), answer_type="MAIN")
        session.add(answer)
        session.flush()
        first = ASRTranscript(answer_id=answer.id, provider="MIMO", model="mimo-v2.5-asr", raw_text="第一个")
        second = ASRTranscript(answer_id=answer.id, provider="MIMO", model="mimo-v2.5-asr", raw_text="第二个")
        session.add_all([first, second])
        session.flush()

        adopt_transcript(session, second, actor_id="reviewer-1")
        session.commit()

        adopted = list(session.scalars(select(ASRTranscript).where(ASRTranscript.is_adopted.is_(True))))
        assert [t.id for t in adopted] == [second.id]
        assert second.adopted_by == "reviewer-1"
        assert second.adopted_at is not None


def test_unknown_rule_ids_are_rejected() -> None:
    """ADR-0001: fabricated/unknown rubric and CE ids never affect formal analysis."""
    validate_known_point_ids(["M1", "I2"], {"M1", "I2", "M3"})
    with pytest.raises(UnknownRuleIdError):
        validate_known_point_ids(["M1", "FAKE"], {"M1"})
    validate_known_critical_error_ids(["CE001"], {"CE001"})
    with pytest.raises(UnknownRuleIdError):
        validate_known_critical_error_ids(["CE001", "NOPE"], {"CE001"})


def test_profile_create_cannot_self_assert_qualification() -> None:
    """MODEL_QUALIFICATION: API_AVAILABLE != QUALIFIED; clients cannot set qualification on create."""
    profile = LLMProfileCreate(provider="OPENAI", model="gpt-x", display_name="d", is_default=True)
    assert not hasattr(profile, "qualification_status")
    with pytest.raises(ValidationError):
        LLMProfileCreate(provider="OPENAI", model="gpt-x", display_name="d", qualification_status="QUALIFIED")


@pytest.fixture
def api_client() -> TestClient:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_profile_creation_forces_untested_status(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/admin/llm-profiles",
        json={"provider": "OPENAI", "model": "gpt-x", "display_name": "d", "is_default": True},
    )
    assert response.status_code == 201
    assert response.json()["qualification_status"] == "UNTESTED"
    assert response.json()["is_default"] is True


def test_profile_creation_rejects_qualification_status_payload(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/admin/llm-profiles",
        json={
            "provider": "OPENAI",
            "model": "gpt-x",
            "display_name": "d",
            "qualification_status": "QUALIFIED",
        },
    )
    assert response.status_code == 422
