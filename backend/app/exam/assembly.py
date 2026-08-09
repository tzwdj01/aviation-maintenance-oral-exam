from __future__ import annotations

from copy import deepcopy
from typing import Any


def lock_attempt_snapshot(plan: dict[str, Any], llm_profile: dict[str, Any], prompt_bundle: dict[str, Any]) -> dict[str, Any]:
    """Produce independent immutable-at-creation snapshots, never live ORM references."""
    return {"plan_snapshot": deepcopy(plan), "llm_profile_snapshot": deepcopy(llm_profile), "prompt_bundle_snapshot": deepcopy(prompt_bundle)}
