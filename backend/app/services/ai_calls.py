from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.security import redact
from app.models.domain import AICall


def create_ai_call(
    session: Session,
    *,
    task_type: str,
    provider: str,
    model: str,
    request_id: str | None = None,
    input_summary: dict[str, Any] | None = None,
    raw_response: dict[str, Any] | None = None,
    status: str = "PENDING",
    error: str | None = None,
    retry_count: int = 0,
    latency_ms: int | None = None,
) -> AICall:
    """Record an auditable provider call; request/response are redacted before persistence."""
    now = datetime.now(UTC)
    terminal = status in {"SUCCEEDED", "FAILED"}
    call = AICall(
        task_type=task_type,
        provider=provider,
        model=model,
        requested_at=now,
        responded_at=now if terminal else None,
        status=status,
        request_id=request_id,
        input_summary=redact(input_summary or {}),
        raw_response=redact(raw_response) if raw_response is not None else None,
        error=error,
        retry_count=retry_count,
        latency_ms=latency_ms,
    )
    session.add(call)
    session.flush()
    return call
