from typing import Any

from sqlalchemy.orm import Session

from app.core.security import redact
from app.models.domain import AuditEvent


def record_audit_event(session: Session, event_type: str, subject_type: str, subject_id: str, payload: dict[str, Any], actor_id: str | None = None) -> AuditEvent:
    event = AuditEvent(actor_id=actor_id, event_type=event_type, subject_type=subject_type, subject_id=subject_id, payload=redact(payload))
    session.add(event)
    return event
