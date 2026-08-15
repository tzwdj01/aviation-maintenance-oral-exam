from __future__ import annotations

from collections.abc import Callable

from app.core.enums import TaskJobState
from app.models.domain import TaskJob


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
