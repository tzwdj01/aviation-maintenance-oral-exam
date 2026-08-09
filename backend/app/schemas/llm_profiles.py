from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LLMProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=256)
    enabled: bool = True
    is_default: bool = False
    qualification_status: str = "UNTESTED"


class LLMProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(default=None, min_length=1, max_length=256)
    enabled: bool | None = None
    is_default: bool | None = None


class LLMProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    provider: str
    model: str
    display_name: str
    enabled: bool
    is_default: bool
    qualification_status: str
    qualification_summary: dict
    qualified_at: datetime | None
    retired_at: datetime | None
