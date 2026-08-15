"""The only mutator for persisted examination and item state."""

from __future__ import annotations

from app.core.enums import AttemptItemState, ExamAttemptState

ATTEMPT_TRANSITIONS = {
    ExamAttemptState.CREATED: {ExamAttemptState.READY, ExamAttemptState.ABANDONED},
    ExamAttemptState.READY: {ExamAttemptState.IN_PROGRESS, ExamAttemptState.ABANDONED},
    ExamAttemptState.IN_PROGRESS: {ExamAttemptState.COMPLETED, ExamAttemptState.MANUAL_REVIEW_REQUIRED, ExamAttemptState.ABANDONED},
    ExamAttemptState.COMPLETED: {ExamAttemptState.MANUAL_REVIEW_REQUIRED, ExamAttemptState.FINALIZED},
    ExamAttemptState.MANUAL_REVIEW_REQUIRED: {ExamAttemptState.FINALIZED, ExamAttemptState.ABANDONED},
    ExamAttemptState.FINALIZED: set(),
    ExamAttemptState.ABANDONED: set(),
}
ITEM_TRANSITIONS = {
    AttemptItemState.PENDING: {AttemptItemState.PRESENTING, AttemptItemState.NEEDS_ATTENTION},
    AttemptItemState.PRESENTING: {AttemptItemState.WAITING_FOR_ANSWER, AttemptItemState.NEEDS_ATTENTION},
    AttemptItemState.WAITING_FOR_ANSWER: {AttemptItemState.ASR_PROCESSING, AttemptItemState.NEEDS_ATTENTION},
    AttemptItemState.ASR_PROCESSING: {AttemptItemState.ANSWER_ANALYZING, AttemptItemState.NEEDS_ATTENTION},
    AttemptItemState.ANSWER_ANALYZING: {AttemptItemState.FOLLOW_UP_PENDING, AttemptItemState.FINAL_ASSESSING, AttemptItemState.NEEDS_ATTENTION},
    AttemptItemState.FOLLOW_UP_PENDING: {AttemptItemState.WAITING_FOR_FOLLOW_UP, AttemptItemState.FINAL_ASSESSING, AttemptItemState.NEEDS_ATTENTION},
    AttemptItemState.WAITING_FOR_FOLLOW_UP: {AttemptItemState.ASR_PROCESSING, AttemptItemState.NEEDS_ATTENTION},
    AttemptItemState.FINAL_ASSESSING: {AttemptItemState.FINALIZED, AttemptItemState.NEEDS_ATTENTION},
    AttemptItemState.FINALIZED: set(),
    AttemptItemState.NEEDS_ATTENTION: {AttemptItemState.ASR_PROCESSING, AttemptItemState.ANSWER_ANALYZING, AttemptItemState.FINAL_ASSESSING},
}


class InvalidTransitionError(ValueError):
    pass


class StateVersionConflictError(ValueError):
    pass


def transition_attempt(attempt: object, target: ExamAttemptState, expected_version: int) -> None:
    current = ExamAttemptState(attempt.state)
    target = ExamAttemptState(target)
    if attempt.state_version != expected_version:
        raise StateVersionConflictError("Attempt state_version does not match")
    if target not in ATTEMPT_TRANSITIONS[current]:
        raise InvalidTransitionError(f"{current} -> {target} is not permitted")
    attempt.state = target.value
    attempt.state_version = expected_version + 1


def transition_item(item: object, target: AttemptItemState, expected_version: int) -> None:
    current = AttemptItemState(item.state)
    target = AttemptItemState(target)
    if item.state_version != expected_version:
        raise StateVersionConflictError("Attempt item state_version does not match")
    if target not in ITEM_TRANSITIONS[current]:
        raise InvalidTransitionError(f"{current} -> {target} is not permitted")
    item.state = target.value
    item.state_version = expected_version + 1
