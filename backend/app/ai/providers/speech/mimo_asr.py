from app.ai.providers.base import (
    AudioReference,
    ProviderFailure,
    ProviderFailureKind,
    TranscriptResult,
)
from app.ai.providers.speech.base import MiMoSpeechBase


class MiMoASRProvider(MiMoSpeechBase):
    """MiMo `mimo-v2.5-asr` adapter.

    Request shape follows the official contract (mimo.mi.com/docs, updated 2026-07-17):
    `messages[].content[].input_audio.data` is a data URL (mp3/wav only) and
    `asr_options.language` selects the recognition language.
    """

    def __init__(
        self,
        base_url: str | None,
        api_key: str | None,
        model: str,
        *,
        language: str = "auto",
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
        self.language = language

    async def transcribe(self, audio: AudioReference) -> TranscriptResult:
        raw, request_id = await self._post(
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {"data": self.audio_data_url(audio)},
                            }
                        ],
                    }
                ],
                "asr_options": {"language": self.language},
            }
        )
        text = ((raw.get("choices") or [{}])[0].get("message") or {}).get("content")
        if not isinstance(text, str) or not text.strip():
            raise ProviderFailure(
                "MiMo ASR returned no text",
                kind=ProviderFailureKind.TEMPORARY,
                code="EMPTY_TRANSCRIPT",
                request_id=request_id,
            )
        return TranscriptResult(text=text, model=self.model, raw_response=raw, request_id=request_id)

    async def synthesize(self, text: str, voice: str | None = None):
        raise NotImplementedError("ASR provider cannot synthesize")
