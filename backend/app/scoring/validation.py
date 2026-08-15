"""Server-side rule-ID validation (ADR-0001).

LLM outputs may only reference published rule IDs from the locked rubric snapshot.
Unknown or fabricated IDs must never affect a formal score.
"""

from __future__ import annotations

from collections.abc import Iterable


class UnknownRuleIdError(ValueError):
    pass


def validate_known_point_ids(point_ids: Iterable[str], known_point_ids: set[str]) -> None:
    unknown = sorted(set(point_ids) - known_point_ids)
    if unknown:
        raise UnknownRuleIdError(f"Unknown rubric point ids: {unknown}")


def validate_known_critical_error_ids(ce_ids: Iterable[str], known_ce_ids: set[str]) -> None:
    unknown = sorted(set(ce_ids) - known_ce_ids)
    if unknown:
        raise UnknownRuleIdError(f"Unknown critical error rule ids: {unknown}")
