from typing import Literal

from app.ai.schemas.common import StrictModel


class FinalAssessmentResponse(StrictModel):
    initial_mastery: Literal["INSUFFICIENT", "PARTIAL", "ADEQUATE", "STRONG", "UNCERTAIN"]
    final_mastery: Literal["INSUFFICIENT", "PARTIAL", "ADEQUATE", "STRONG", "UNCERTAIN"]
    prompt_dependency: Literal["A", "B", "C", "D"]
    qualitative_summary: str
