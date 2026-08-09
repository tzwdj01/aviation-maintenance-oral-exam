from __future__ import annotations

import base64
from typing import Any

import httpx

from app.ai.providers.base import AudioReference, ProviderFailure


class MiMoSpeechBase:
    provider_name = "MIMO"

    def __init__(self, base_url: str | None, api_key: str | None, model: str, timeout_seconds: float = 60) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key, self.model = api_key, model
        self.timeout = httpx.Timeout(timeout_seconds, connect=min(10, timeout_seconds))

    async def _post(self, payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        if not self.base_url or not self.api_key:
            raise ProviderFailure("MiMo speech credentials are not configured")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/chat/completions", json=payload, headers={"Authorization": f"Bearer {self.api_key}"})
                response.raise_for_status()
                return response.json(), response.headers.get("x-request-id") or response.headers.get("request-id")
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderFailure(f"MiMo speech request failed: {exc}") from exc

    @staticmethod
    def audio_data_url(audio: AudioReference) -> str:
        return f"data:{audio.mime_type};base64," + base64.b64encode(audio.content).decode("ascii")
