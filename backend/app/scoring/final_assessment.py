from dataclasses import dataclass


@dataclass(frozen=True)
class FinalAssessmentView:
    initial_mastery: str
    final_mastery: str
    prompt_dependency: str
    qualitative_summary: str
