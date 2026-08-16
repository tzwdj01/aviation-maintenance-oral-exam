from __future__ import annotations

import base64

from app.ai.providers.base import ProviderFailure, ProviderFailureKind, SynthesizedAudio
from app.ai.providers.speech.base import MiMoSpeechBase


class MiMoVoiceDesignProvider(MiMoSpeechBase):
    """Optional MiMo `mimo-v2.5-tts-voicedesign` capability (feature-gated).

    Official contract (mimo.mi.com/docs, updated 2026-07-17): the `user` message carries the
    text describing the voice design and `audio.voice` is NOT supported (the earlier HTTP 400
    was caused by sending that field). `audio.optimize_text_preview` is only valid for this
    model. The capability stays disabled until separately qualified (docs/qualification/).
    """

    provider_name = "MIMO"

    def __init__(
        self,
        *,
        enabled: bool = False,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str = "mimo-v2.5-tts-voicedesign",
        optimize_text_preview: bool = False,
        connect_timeout_seconds: float = 10,
        request_timeout_seconds: float = 60,
    ) -> None:
        super().__init__(
            base_url,
            api_key,
            model,
            connect_timeout_seconds=connect_timeout_seconds,
            request_timeout_seconds=request_timeout_seconds,
        )
        self.enabled = enabled
        self.optimize_text_preview = optimize_text_preview

    async def design_voice(self, design_text: str, target_text: str) -> SynthesizedAudio:
        """Synthesize `target_text` in a voice designed from `design_text`."""
        if not self.enabled:
            raise ProviderFailure(
                "Voice Design is feature-gated until separately qualified",
                kind=ProviderFailureKind.PERMANENT,
                code="FEATURE_GATED",
            )
        audio: dict[str, object] = {"format": "wav"}
        messages: list[dict[str, str]] = [{"role": "user", "content": design_text}]
        if self.optimize_text_preview:
            audio["optimize_text_preview"] = True
        else:
            messages.append({"role": "assistant", "content": target_text})
        raw, request_id = await self._post({"model": self.model, "messages": messages, "audio": audio})
        message_audio = (((raw.get("choices") or [{}])[0].get("message") or {}).get("audio") or {})
        encoded = message_audio.get("data") or (raw.get("audio") or {}).get("data")
        if not isinstance(encoded, str):
            raise ProviderFailure(
                "MiMo Voice Design response lacks audio data",
                kind=ProviderFailureKind.TEMPORARY,
                code="EMPTY_AUDIO",
                request_id=request_id,
            )
        return SynthesizedAudio(
            content=base64.b64decode(encoded),
            mime_type="audio/wav",
            model=self.model,
            raw_response=raw,
            request_id=request_id,
        )
