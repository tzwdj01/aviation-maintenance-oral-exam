from typing import Literal

from pydantic import Field

from app.ai.schemas.common import EvidenceQuote, StrictModel


class CoveragePointAssessment(StrictModel):
    point_id: str
    status: Literal["covered", "partial", "missing", "uncertain"]
    evidence_quotes: list[EvidenceQuote] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str = Field(min_length=1)


class CoverageResponse(StrictModel):
    point_assessments: list[CoveragePointAssessment]
