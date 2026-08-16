from __future__ import annotations

from collections.abc import Callable

from app.core.enums import TaskJobState
from app.models.domain import TaskJob


def backoff_seconds(
    attempts: int,
    *,
    base_seconds: float = 1.0,
    factor: float = 2.0,
    max_seconds: float = 30.0,
) -> float:
    """Exponential backoff for retry scheduling (starts at base for the first retry)."""
    if attempts <= 1:
        return 0.0
    return min(max_seconds, base_seconds * (factor ** (attempts - 2)))


def run_fake_worker(job: TaskJob, handler: Callable[[dict], None]) -> TaskJob:
    """Development-only worker shape; the DB job remains source of truth after any outcome."""
    job.state = TaskJobState.RUNNING.value
    job.attempts += 1
    try:
        handler(job.payload)
    except (OSError, RuntimeError, ValueError) as exc:
        job.state = TaskJobState.FAILED.value
        job.last_error = str(exc)
    else:
        job.state = TaskJobState.SUCCEEDED.value
        job.last_error = None
    return job
