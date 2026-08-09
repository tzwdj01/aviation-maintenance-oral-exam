"""SQLAlchemy 2.x persistence model for the Sprint 1A audit trail.

Published versions are protected in service/repository methods.  Versioned records are never updated by
runtime exam operations; attempts persist snapshots so later publication cannot rewrite history.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class UUIDTimestampMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PublishableVersionMixin:
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[str | None] = mapped_column(String(128))


class Question(UUIDTimestampMixin, Base):
    __tablename__ = "questions"
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class QuestionVersion(UUIDTimestampMixin, PublishableVersionMixin, Base):
    __tablename__ = "question_versions"
    __table_args__ = (UniqueConstraint("question_id", "version", name="uq_question_version"),)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"), nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    immutable_hash: Mapped[str | None] = mapped_column(String(64))


class ScoringRubric(UUIDTimestampMixin, Base):
    __tablename__ = "scoring_rubrics"
    question_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("question_versions.id"), unique=True, nullable=False)
    rubric_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False)


class RubricPoint(UUIDTimestampMixin, Base):
    __tablename__ = "rubric_points"
    __table_args__ = (UniqueConstraint("rubric_id", "point_code", name="uq_rubric_point_code"),)
    rubric_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scoring_rubrics.id"), nullable=False)
    point_code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evaluation_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    partial_weight: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)


class CriticalErrorRule(UUIDTimestampMixin, Base):
    __tablename__ = "critical_error_rules"
    __table_args__ = (UniqueConstraint("rubric_id", "critical_error_code", name="uq_ce_rule_code"),)
    rubric_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scoring_rubrics.id"), nullable=False)
    critical_error_code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    review_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ReferenceSource(UUIDTimestampMixin, Base):
    __tablename__ = "reference_sources"
    question_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("question_versions.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    citation: Mapped[str] = mapped_column(Text, nullable=False)
    locator: Mapped[str | None] = mapped_column(String(256))


class FollowUpTopic(UUIDTimestampMixin, Base):
    __tablename__ = "follow_up_topics"
    question_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("question_versions.id"), nullable=False)
    topic_code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    max_follow_ups: Mapped[int] = mapped_column(Integer, default=2, nullable=False)


class Vocabulary(UUIDTimestampMixin, Base):
    __tablename__ = "vocabularies"
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)


class VocabularyVersion(UUIDTimestampMixin, PublishableVersionMixin, Base):
    __tablename__ = "vocabulary_versions"
    __table_args__ = (UniqueConstraint("vocabulary_id", "version", name="uq_vocabulary_version"),)
    vocabulary_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vocabularies.id"), nullable=False)


class VocabularyTerm(UUIDTimestampMixin, Base):
    __tablename__ = "vocabulary_terms"
    vocabulary_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vocabulary_versions.id"), nullable=False)
    canonical_text: Mapped[str] = mapped_column(String(256), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    context_hints: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)


class ExamPlan(UUIDTimestampMixin, Base):
    __tablename__ = "exam_plans"
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ExamPlanVersion(UUIDTimestampMixin, PublishableVersionMixin, Base):
    __tablename__ = "exam_plan_versions"
    __table_args__ = (UniqueConstraint("exam_plan_id", "version", name="uq_exam_plan_version"),)
    exam_plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_plans.id"), nullable=False)
    passing_policy: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)


class ExamBlueprintSection(UUIDTimestampMixin, Base):
    __tablename__ = "exam_blueprint_sections"
    exam_plan_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_plan_versions.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)


class ExamQuestionPool(UUIDTimestampMixin, Base):
    __tablename__ = "exam_question_pools"
    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_blueprint_sections.id"), nullable=False)
    question_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("question_versions.id"), nullable=False)


class ExamSelectionRule(UUIDTimestampMixin, Base):
    __tablename__ = "exam_selection_rules"
    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_blueprint_sections.id"), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)


class LLMProfile(UUIDTimestampMixin, Base):
    __tablename__ = "llm_profiles"
    provider: Mapped[str] = mapped_column(String(64), nullable=False)  # String deliberately permits future providers.
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    qualification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNTESTED")
    qualification_summary: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PromptVersion(UUIDTimestampMixin, PublishableVersionMixin, Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("task_type", "version", name="uq_prompt_task_version"),)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    template_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class ExamAttempt(UUIDTimestampMixin, Base):
    __tablename__ = "exam_attempts"
    exam_plan_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_plan_versions.id"), nullable=False)
    llm_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("llm_profiles.id"), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="CREATED")
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    plan_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    llm_profile_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    prompt_bundle_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    candidate_reference: Mapped[str | None] = mapped_column(String(128))


class AttemptItem(UUIDTimestampMixin, Base):
    __tablename__ = "attempt_items"
    __table_args__ = (UniqueConstraint("attempt_id", "sequence", name="uq_attempt_item_sequence"),)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_attempts.id"), nullable=False)
    question_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("question_versions.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    question_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    rubric_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)


class FollowUp(UUIDTimestampMixin, Base):
    __tablename__ = "follow_ups"
    attempt_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempt_items.id"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    target_point_codes: Mapped[list[str]] = mapped_column(JSONType, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)


class Answer(UUIDTimestampMixin, Base):
    __tablename__ = "answers"
    attempt_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempt_items.id"), nullable=False)
    follow_up_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("follow_ups.id"))
    answer_type: Mapped[str] = mapped_column(String(32), nullable=False)
    supersedes_answer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("answers.id"))
    audio_uri: Mapped[str | None] = mapped_column(Text)
    audio_sha256: Mapped[str | None] = mapped_column(String(64))


class ASRTranscript(UUIDTimestampMixin, Base):
    __tablename__ = "asr_transcripts"
    answer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("answers.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    language: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(6, 5))
    is_adopted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    adopted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    adopted_by: Mapped[str | None] = mapped_column(String(128))


class ASRNormalization(UUIDTimestampMixin, Base):
    __tablename__ = "asr_normalizations"
    transcript_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("asr_transcripts.id"), nullable=False)
    vocabulary_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vocabulary_versions.id"), nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)


class NormalizationMapping(UUIDTimestampMixin, Base):
    __tablename__ = "normalization_mappings"
    normalization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("asr_normalizations.id"), nullable=False)
    raw_fragment: Mapped[str] = mapped_column(String(256), nullable=False)
    normalized_fragment: Mapped[str] = mapped_column(String(256), nullable=False)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    normalization_rule: Mapped[str] = mapped_column(String(64), nullable=False)
    vocabulary_term_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vocabulary_terms.id"))


class EvidenceSpan(UUIDTimestampMixin, Base):
    __tablename__ = "evidence_spans"
    transcript_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("asr_transcripts.id"), nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    start_char: Mapped[int | None] = mapped_column(Integer)
    end_char: Mapped[int | None] = mapped_column(Integer)
    resolution_status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_analysis_type: Mapped[str] = mapped_column(String(64), nullable=False)


class KnowledgePointAnalysis(UUIDTimestampMixin, Base):
    __tablename__ = "knowledge_point_analyses"
    attempt_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempt_items.id"), nullable=False)
    answer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("answers.id"), nullable=False)
    rubric_point_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rubric_points.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(6, 5))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    ai_call_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_calls.id"))


class CriticalErrorAnalysis(UUIDTimestampMixin, Base):
    __tablename__ = "critical_error_analyses"
    attempt_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempt_items.id"), nullable=False)
    answer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("answers.id"), nullable=False)
    critical_error_rule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("critical_error_rules.id"), nullable=False)
    raw_result: Mapped[str] = mapped_column(String(32), nullable=False)
    aggregate_result: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    ai_call_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_calls.id"))


class QuestionFinalAssessment(UUIDTimestampMixin, Base):
    __tablename__ = "question_final_assessments"
    attempt_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempt_items.id"), unique=True, nullable=False)
    initial_mastery: Mapped[str] = mapped_column(String(32), nullable=False)
    final_mastery: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_dependency: Mapped[str] = mapped_column(String(1), nullable=False)
    qualitative_summary: Mapped[str] = mapped_column(Text, nullable=False)
    ai_call_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_calls.id"))


class ScoreEvaluation(UUIDTimestampMixin, Base):
    __tablename__ = "score_evaluations"
    attempt_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempt_items.id"), nullable=False)
    calculation_stage: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    calculation_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)


class ExamFinalResult(UUIDTimestampMixin, Base):
    __tablename__ = "exam_final_results"
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_attempts.id"), unique=True, nullable=False)
    final_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    report_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)


class AICall(UUIDTimestampMixin, Base):
    __tablename__ = "ai_calls"
    llm_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("llm_profiles.id"))
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("prompt_versions.id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(256))
    input_summary: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    error: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class TaskJob(UUIDTimestampMixin, Base):
    __tablename__ = "task_jobs"
    __table_args__ = (UniqueConstraint("business_key", name="uq_task_job_business_key"),)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    business_key: Mapped[str] = mapped_column(String(256), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)


class IdempotencyRecord(UUIDTimestampMixin, Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("actor_id", "idempotency_key", name="uq_idempotency_actor_key"),)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)


class ReviewDecision(UUIDTimestampMixin, Base):
    __tablename__ = "review_decisions"
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_attempts.id"), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)


class ReviewDecisionItem(UUIDTimestampMixin, Base):
    __tablename__ = "review_decision_items"
    review_decision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("review_decisions.id"), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(128), nullable=False)
    original_value: Mapped[str] = mapped_column(Text, nullable=False)
    human_value: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)


class AuditEvent(UUIDTimestampMixin, Base):
    __tablename__ = "audit_events"
    actor_id: Mapped[str | None] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
