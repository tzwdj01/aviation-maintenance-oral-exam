import base64

from app.ai.providers.base import (
    AudioReference,
    ProviderFailure,
    ProviderFailureKind,
    SynthesizedAudio,
)
from app.ai.providers.speech.base import MiMoSpeechBase


class MiMoTTSProvider(MiMoSpeechBase):
    """MiMo `mimo-v2.5-tts` adapter.

    Request shape follows the official contract (mimo.mi.com/docs, updated 2026-07-17):
    the `assistant` message carries the target text and `audio.format`/`audio.voice` select
    the output format and built-in voice. Synthesized audio is returned in
    `choices[0].message.audio.data` (base64).
    """

    def __init__(
        self,
        base_url: str | None,
        api_key: str | None,
        model: str,
        *,
        voice: str = "mimo_default",
        audio_format: str = "wav",
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
        self.voice = voice
        self.audio_format = audio_format

    async def synthesize(self, text: str, voice: str | None = None) -> SynthesizedAudio:
        raw, request_id = await self._post(
            {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": "请使用清晰、自然、专业的中文口试考官语气。"},
                    {"role": "assistant", "content": text},
                ],
                "audio": {"format": self.audio_format, "voice": voice or self.voice},
            }
        )
        message_audio = (((raw.get("choices") or [{}])[0].get("message") or {}).get("audio") or {})
        encoded = message_audio.get("data") or (raw.get("audio") or {}).get("data")
        if not isinstance(encoded, str):
            raise ProviderFailure(
                "MiMo TTS response lacks audio data",
                kind=ProviderFailureKind.TEMPORARY,
                code="EMPTY_AUDIO",
                request_id=request_id,
            )
        try:
            content = base64.b64decode(encoded)
        except ValueError as exc:
            raise ProviderFailure(
                "MiMo TTS returned malformed audio",
                kind=ProviderFailureKind.TEMPORARY,
                code="MALFORMED_AUDIO",
                request_id=request_id,
            ) from exc
        if not content:
            raise ProviderFailure(
                "MiMo TTS returned empty audio",
                kind=ProviderFailureKind.TEMPORARY,
                code="EMPTY_AUDIO",
                request_id=request_id,
            )
        mime_type = "audio/mpeg" if self.audio_format == "mp3" else "audio/wav"
        return SynthesizedAudio(
            content=content,
            mime_type=mime_type,
            model=self.model,
            raw_response=raw,
            request_id=request_id,
        )

    async def transcribe(self, audio: AudioReference):
        raise NotImplementedError("TTS provider cannot transcribe")
