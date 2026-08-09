from collections.abc import Iterable


def aggregate_critical_error(raw_results: Iterable[str], human_override: str | None = None) -> str:
    """A historical AI trigger is sticky; it can only be superseded by a recorded human decision."""
    if human_override is not None:
        return "OVERRIDDEN_BY_HUMAN"
    values = list(raw_results)
    if "TRIGGERED" in values:
        return "TRIGGERED"
    if "UNCERTAIN" in values:
        return "UNCERTAIN"
    return "NOT_TRIGGERED"
