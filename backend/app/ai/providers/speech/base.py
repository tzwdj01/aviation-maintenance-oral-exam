from __future__ import annotations

import base64
from typing import Any

import httpx

from app.ai.providers.base import (
    AudioReference,
    ProviderFailure,
    ProviderFailureKind,
    map_provider_error,
)


class MiMoSpeechBase:
    provider_name = "MIMO"

    def __init__(
        self,
        base_url: str | None,
        api_key: str | None,
        model: str,
        *,
        connect_timeout_seconds: float = 10,
        request_timeout_seconds: float = 60,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key, self.model = api_key, model
        self.timeout = httpx.Timeout(request_timeout_seconds, connect=connect_timeout_seconds)

    async def _post(self, payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        if not self.base_url or not self.api_key:
            raise ProviderFailure(
                "MiMo speech credentials are not configured",
                kind=ProviderFailureKind.PERMANENT,
                code="CREDENTIALS_MISSING",
            )
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                response.raise_for_status()
                request_id = response.headers.get("x-request-id") or response.headers.get("request-id")
                try:
                    body = response.json()
                except ValueError as exc:
                    raise ProviderFailure(
                        "MiMo speech returned a non-JSON response",
                        kind=ProviderFailureKind.TEMPORARY,
                        code="INVALID_RESPONSE",
                        request_id=request_id,
                    ) from exc
                return body, request_id
        except ProviderFailure:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise map_provider_error(exc) from exc

    @staticmethod
    def audio_data_url(audio: AudioReference) -> str:
        return f"data:{audio.mime_type};base64," + base64.b64encode(audio.content).decode("ascii")
