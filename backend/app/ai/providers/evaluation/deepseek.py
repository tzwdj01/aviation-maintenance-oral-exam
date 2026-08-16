from __future__ import annotations

from typing import Any

from app.ai.providers.base import EvaluationRequest, ProviderResponse
from app.ai.providers.evaluation.base import StructuredEvaluationProvider


class DeepSeekEvaluationProvider(StructuredEvaluationProvider):
    """OpenAI-compatible chat endpoint with JSON mode plus local strict Pydantic validation.

    The adapter intentionally treats JSON mode as transport assistance, not proof of a valid decision.
    """
    provider_name = "DEEPSEEK"

    async def _evaluate(self, request: EvaluationRequest[Any]) -> ProviderResponse[Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": self._user_content(request)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "stream": False,
        }
        raw, request_id = await self._post("/chat/completions", payload)
        value = self._parse(raw["choices"][0]["message"]["content"], request, raw, request_id)
        return ProviderResponse(value=value.value, model=self.model, request_id=request_id, raw_response=raw)
