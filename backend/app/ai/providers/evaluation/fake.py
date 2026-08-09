from __future__ import annotations

from typing import Any

from app.ai.providers.base import EvaluationRequest, ProviderResponse


class FakeEvaluationProvider:
    provider_name = "FAKE"
    model = "fake-evaluation-v1"

    def __init__(self, payloads: dict[str, dict[str, Any]] | None = None) -> None:
        self.payloads = payloads or {}

    async def _evaluate(self, request: EvaluationRequest[Any]) -> ProviderResponse[Any]:
        payload = self.payloads.get(request.task_type, {})
        return ProviderResponse(value=request.output_type.model_validate(payload), model=self.model, request_id="fake-request", raw_response=payload)

    evaluate_coverage = _evaluate
    detect_critical_errors = _evaluate
    evaluate_quality_risk = _evaluate
    decide_follow_up = _evaluate
    final_assessment = _evaluate
