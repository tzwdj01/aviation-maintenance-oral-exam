from pydantic import Field, model_validator

from app.ai.schemas.common import StrictModel


class FollowUpResponse(StrictModel):
    should_ask: bool
    target_point_ids: list[str] = Field(default_factory=list)
    follow_up_question: str | None = None
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def check_shape(self) -> "FollowUpResponse":
        if self.should_ask and (not self.target_point_ids or not self.follow_up_question):
            raise ValueError("A follow-up needs targets and an open question")
        if not self.should_ask and (self.target_point_ids or self.follow_up_question is not None):
            raise ValueError("No follow-up must have empty targets and null question")
        return self
