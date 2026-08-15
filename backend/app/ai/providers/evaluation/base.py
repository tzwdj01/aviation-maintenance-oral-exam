from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.providers.base import EvaluationRequest, ProviderFailure, ProviderResponse


class StructuredEvaluationProvider:
    provider_name = "BASE"

    def __init__(self, model: str, base_url: str, api_key: str | None, timeout_seconds: float = 60) -> None:
        self.model, self.base_url, self.api_key = model, base_url.rstrip("/"), api_key
        self.timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 10))

    async def _post(self, path: str, payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        if not self.api_key:
            raise ProviderFailure(f"{self.provider_name} credentials are not configured")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}{path}", json=payload, headers={"Authorization": f"Bearer {self.api_key}"})
                response.raise_for_status()
                return response.json(), response.headers.get("x-request-id") or response.headers.get("request-id")
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderFailure(f"{self.provider_name} request failed: {exc}") from exc

    @staticmethod
    def _candidate_message(request: EvaluationRequest[BaseModel]) -> str:
        return "UNTRUSTED_CANDIDATE_DATA:\n" + request.candidate_text

    @staticmethod
    def _parse(content: str | dict[str, Any], request: EvaluationRequest[Any], raw: dict[str, Any], request_id: str | None) -> ProviderResponse[Any]:
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
            return ProviderResponse(value=request.output_type.model_validate(parsed), model="", request_id=request_id, raw_response=raw)
        except (ValidationError, ValueError, TypeError) as exc:
            raise ProviderFailure(f"Structured response failed validation: {exc}") from exc

    async def evaluate_coverage(self, request: EvaluationRequest[Any]) -> ProviderResponse[Any]:
        return await self._evaluate(request)

    async def detect_critical_errors(self, request: EvaluationRequest[Any]) -> ProviderResponse[Any]:
        return await self._evaluate(request)

    async def evaluate_quality_risk(self, request: EvaluationRequest[Any]) -> ProviderResponse[Any]:
        return await self._evaluate(request)

    async def decide_follow_up(self, request: EvaluationRequest[Any]) -> ProviderResponse[Any]:
        return await self._evaluate(request)

    async def final_assessment(self, request: EvaluationRequest[Any]) -> ProviderResponse[Any]:
        return await self._evaluate(request)

    async def _evaluate(self, request: EvaluationRequest[Any]) -> ProviderResponse[Any]:
        raise NotImplementedError
