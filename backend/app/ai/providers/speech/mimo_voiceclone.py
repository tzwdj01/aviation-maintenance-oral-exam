from __future__ import annotations

import base64

from app.ai.providers.base import (
    AudioReference,
    ProviderFailure,
    ProviderFailureKind,
    SynthesizedAudio,
)
from app.ai.providers.speech.base import MiMoSpeechBase


class MiMoVoiceCloneProvider(MiMoSpeechBase):
    """Optional MiMo `mimo-v2.5-tts-voiceclone` capability (feature-gated).

    Official contract (mimo.mi.com/docs, updated 2026-07-17): `audio.voice` is required and
    must be the base64 encoding of an audio sample in mp3 or wav format. The capability stays
    disabled until an authorized reference flow is confirmed and separately qualified.
    """

    provider_name = "MIMO"

    def __init__(
        self,
        *,
        enabled: bool = False,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str = "mimo-v2.5-tts-voiceclone",
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

    async def clone_voice(self, target_text: str, sample: AudioReference) -> SynthesizedAudio:
        """Synthesize `target_text` in a voice cloned from the `sample` audio reference."""
        if not self.enabled:
            raise ProviderFailure(
                "Voice Clone is feature-gated until an authorized reference flow is confirmed and qualified",
                kind=ProviderFailureKind.PERMANENT,
                code="FEATURE_GATED",
            )
        if sample.mime_type not in {"audio/wav", "audio/mpeg"}:
            raise ProviderFailure(
                "Voice Clone requires an mp3 or wav audio sample",
                kind=ProviderFailureKind.PERMANENT,
                code="INVALID_SAMPLE",
            )
        raw, request_id = await self._post(
            {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": "请使用该音色朗读目标文本。"},
                    {"role": "assistant", "content": target_text},
                ],
                "audio": {
                    "format": "wav",
                    "voice": base64.b64encode(sample.content).decode("ascii"),
                },
            }
        )
        message_audio = (((raw.get("choices") or [{}])[0].get("message") or {}).get("audio") or {})
        encoded = message_audio.get("data") or (raw.get("audio") or {}).get("data")
        if not isinstance(encoded, str):
            raise ProviderFailure(
                "MiMo Voice Clone response lacks audio data",
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
