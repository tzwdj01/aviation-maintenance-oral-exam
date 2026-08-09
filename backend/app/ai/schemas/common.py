from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EvidenceQuote(StrictModel):
    quote: str = Field(min_length=1, max_length=1000)
