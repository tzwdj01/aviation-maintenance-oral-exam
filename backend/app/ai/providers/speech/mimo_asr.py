from app.ai.providers.base import AudioReference, TranscriptResult
from app.ai.providers.speech.base import MiMoSpeechBase


class MiMoASRProvider(MiMoSpeechBase):
    async def transcribe(self, audio: AudioReference) -> TranscriptResult:
        raw, request_id = await self._post({
            "model": self.model,
            "messages": [{"role": "user", "content": [{"type": "input_audio", "input_audio": {"data": self.audio_data_url(audio)}}]}],
            "asr_options": {"language": "zh"}, "stream": False,
        })
        text = ((raw.get("choices") or [{}])[0].get("message") or {}).get("content")
        if not isinstance(text, str) or not text.strip():
            from app.ai.providers.base import ProviderFailure
            raise ProviderFailure("MiMo ASR returned no text")
        return TranscriptResult(text=text, model=self.model, raw_response=raw, request_id=request_id)

    async def synthesize(self, text: str, voice: str | None = None):
        raise NotImplementedError("ASR provider cannot synthesize")
