from __future__ import annotations

from typing import Any

from app.ai.providers.base import EvaluationRequest, ProviderResponse
from app.ai.providers.evaluation.base import StructuredEvaluationProvider


class OpenAIEvaluationProvider(StructuredEvaluationProvider):
    """Uses Responses API `text.format=json_schema` and validates independently after receipt."""
    provider_name = "OPENAI"

    async def _evaluate(self, request: EvaluationRequest[Any]) -> ProviderResponse[Any]:
        payload = {
            "model": self.model,
            "instructions": request.system_prompt,
            "input": self._candidate_message(request),
            "text": {"format": {"type": "json_schema", "name": request.task_type.lower(), "strict": True, "schema": request.output_type.model_json_schema()}},
        }
        raw, request_id = await self._post("/responses", payload)
        content = raw.get("output_text")
        if content is None:
            for output in raw.get("output", []):
                for part in output.get("content", []):
                    if part.get("type") in {"output_text", "refusal"}:
                        content = part.get("text")
                        break
        value = self._parse(content, request, raw, request_id)
        return ProviderResponse(value=value.value, model=self.model, request_id=request_id, raw_response=raw)
