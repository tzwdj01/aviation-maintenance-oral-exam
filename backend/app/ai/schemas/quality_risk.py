from typing import Literal

from pydantic import Field, model_validator

from app.ai.schemas.common import EvidenceQuote, StrictModel


class QualityRiskPointAssessment(StrictModel):
    point_id: str
    status: Literal["covered", "partial", "missing", "uncertain"]
    evidence_quotes: list[EvidenceQuote] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def credit_bearing_needs_evidence(self) -> "QualityRiskPointAssessment":
        if self.status in {"covered", "partial"} and not self.evidence_quotes:
            raise ValueError(f"{self.status} requires an evidence quote")
        return self


class QualityRiskResponse(StrictModel):
    quality_risk_assessments: list[QualityRiskPointAssessment]
