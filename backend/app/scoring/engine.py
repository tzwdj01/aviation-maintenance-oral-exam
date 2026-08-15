from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal


def calculate_score(points: Iterable[Mapping[str, object]]) -> Decimal:
    """Formal score: deterministic Decimal only; missing and uncertain never receive credit."""
    total = Decimal(0)
    for point in points:
        status = str(point["status"])
        if status == "covered":
            total += Decimal(str(point["weight"]))
        elif status == "partial":
            total += Decimal(str(point["partial_weight"]))
    return total


def select_initial_analysis(analyses: Iterable[Mapping[str, object]]) -> list[Mapping[str, object]]:
    """Only the first adopted MAIN answer establishes initial-response scoring."""
    return [row for row in analyses if row.get("answer_type") == "MAIN" and row.get("is_first_adopted_main") is True]
