"""Explicit local development seed; no provider credentials are stored."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import LLMProfile, Question, QuestionVersion, RubricPoint, ScoringRubric


def seed_development_data(session: Session) -> None:
    if not session.scalar(select(LLMProfile).where(LLMProfile.provider == "MIMO", LLMProfile.model == "mimo-v2.5")):
        session.add(LLMProfile(provider="MIMO", model="mimo-v2.5", display_name="MiMo V2.5 (not qualified judge)", enabled=True, is_default=False, qualification_status="FAILED", qualification_summary={"source": "qualification_v2_full", "reason": "formal judge thresholds not met"}))
    for provider, model, display_name, is_default in [("DEEPSEEK", "deepseek-v4-pro", "DeepSeek (unqualified)", True), ("OPENAI", "gpt-5", "OpenAI (unqualified)", False)]:
        if not session.scalar(select(LLMProfile).where(LLMProfile.provider == provider, LLMProfile.model == model)):
            session.add(LLMProfile(provider=provider, model=model, display_name=display_name, enabled=True, is_default=is_default, qualification_status="UNTESTED", qualification_summary={}))
    if not session.scalar(select(Question).where(Question.code == "DEMO-GENERAL-001")):
        question = Question(code="DEMO-GENERAL-001", title="Demo non-operational question")
        session.add(question)
        session.flush()
        version = QuestionVersion(question_id=question.id, version=1, status="DRAFT", stem="请说明你如何核对一项工作已经完成。", scope={"demo_only": True})
        session.add(version)
        session.flush()
        rubric = ScoringRubric(question_version_id=version.id, rubric_version=1, status="DRAFT")
        session.add(rubric)
        session.flush()
        session.add(RubricPoint(rubric_id=rubric.id, point_code="DEMO-VERIFY", description="说明需核对受控记录", evaluation_mode="COVERAGE", weight=10, partial_weight=5, display_order=1))
    session.commit()
