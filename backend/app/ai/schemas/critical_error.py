from typing import Literal

from pydantic import Field, model_validator

from app.ai.schemas.common import EvidenceQuote, StrictModel


class CriticalErrorAssessment(StrictModel):
    critical_error_id: str
    result: Literal["NOT_TRIGGERED", "TRIGGERED", "UNCERTAIN"]
    evidence_quotes: list[EvidenceQuote] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def triggered_needs_evidence(self) -> "CriticalErrorAssessment":
        if self.result == "TRIGGERED" and not self.evidence_quotes:
            raise ValueError("TRIGGERED requires an evidence quote")
        return self


class CriticalErrorResponse(StrictModel):
    critical_error_assessments: list[CriticalErrorAssessment]
