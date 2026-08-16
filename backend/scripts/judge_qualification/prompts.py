"""Versioned Prompt Bundle for the Sprint 1C Judge Qualification.

All providers receive the exact same system prompts for every pass. Changing a prompt is a
Prompt Bundle change: bump the version and record it (docs/qualification/MODEL_QUALIFICATION.md
§5) — never tweak prompts per provider to improve one model's score.
"""

from __future__ import annotations

from typing import Any

PROMPT_BUNDLE_VERSION = "prompt-bundle-v1"

_PROMPTS: dict[str, str] = {
    "COVERAGE": (
        "你是航空维修口试评分辅助。根据题目与评分标准判断考生回答对每个知识点的覆盖情况。"
        "每个点只能输出 covered/partial/missing/uncertain 之一；covered/partial 必须给出"
        "考生原话中的逐字证据引文（evidence_quotes）。不要输出数字分数，不要创建评分标准之外的新知识点。"
    ),
    "CRITICAL_ERROR": (
        "你是航空维修口试安全检查员。仅根据给出的 Critical Error 规则判断是否触发。"
        "每个规则只能输出 NOT_TRIGGERED/TRIGGERED/UNCERTAIN 之一；TRIGGERED 必须给出考生原话的逐字证据引文。"
    ),
    "QUALITY_RISK": (
        "你是航空维修口试的质量与风险意识评估。根据题目与评分标准评估考生的风险意识与表达质量。"
        "每个点只能输出 covered/partial/missing/uncertain 之一；covered/partial 必须给出逐字证据引文。"
    ),
    "FOLLOW_UP": (
        "你是口试追问决策。根据当前覆盖与错误分析决定是否需要追问。"
        "需要追问时 must 给出 target_point_ids 与开放式 follow_up_question；不需要时 should_ask=false、"
        "target_point_ids 为空、follow_up_question 为 null。追问只补充当前题目的缺失知识点，不得创建新评分标准。"
    ),
    "FINAL_ASSESSMENT": (
        "你是口试最终评估。给出 initial_mastery/final_mastery（INSUFFICIENT/PARTIAL/ADEQUATE/STRONG/UNCERTAIN）"
        "与 prompt_dependency（A=无需追问即完整；B=一次轻度追问后完整；C=需明显追问才完整；D=追问后仍未掌握）。"
        "只输出定性评估，不要输出数字分数。"
    ),
}


def system_prompt_for(task_type: str) -> str:
    try:
        return _PROMPTS[task_type]
    except KeyError as exc:  # pragma: no cover
        raise ValueError(f"unknown task type: {task_type}") from exc


def prompt_bundle_snapshot() -> dict[str, Any]:
    return {"version": PROMPT_BUNDLE_VERSION, "pass_prompts": dict(_PROMPTS)}
