from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import request_hash
from app.models.domain import ASRTranscript, IdempotencyRecord, LLMProfile


class IdempotencyConflictError(ValueError):
    pass


def execute_idempotently(
    session: Session, actor_id: str, key: str, payload: Any, handler: Callable[[], tuple[int, dict[str, Any]]]
) -> tuple[int, dict[str, Any], bool]:
    digest = request_hash(payload)
    existing = session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.actor_id == actor_id, IdempotencyRecord.idempotency_key == key
        )
    )
    if existing:
        if existing.request_hash != digest:
            raise IdempotencyConflictError("Idempotency-Key was already used with a different request body")
        return existing.response_status, existing.response_body, True
    status, body = handler()
    session.add(
        IdempotencyRecord(
            actor_id=actor_id,
            idempotency_key=key,
            request_hash=digest,
            response_status=status,
            response_body=body,
        )
    )
    return status, body, False


def adopt_transcript(session: Session, transcript: ASRTranscript, actor_id: str) -> ASRTranscript:
    """Adoption is explicit and preserves every raw ASR result."""
    for sibling in session.scalars(
        select(ASRTranscript).where(ASRTranscript.answer_id == transcript.answer_id)
    ):
        sibling.is_adopted = False
    transcript.is_adopted = True
    transcript.adopted_by = actor_id
    transcript.adopted_at = datetime.now(UTC)
    return transcript


def update_llm_profile_presentation(
    session: Session,
    profile: LLMProfile,
    *,
    display_name: str | None,
    enabled: bool | None,
    is_default: bool | None,
) -> LLMProfile:
    """Qualification results are immutable; only operational presentation/default settings change here."""
    if display_name is not None:
        profile.display_name = display_name
    if enabled is not None:
        profile.enabled = enabled
    if is_default:
        for other in session.scalars(select(LLMProfile).where(LLMProfile.id != profile.id)):
            other.is_default = False
        profile.is_default = True
    elif is_default is False:
        profile.is_default = False
    return profile
