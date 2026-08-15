import base64

from app.ai.providers.base import AudioReference, ProviderFailure, SynthesizedAudio
from app.ai.providers.speech.base import MiMoSpeechBase


class MiMoTTSProvider(MiMoSpeechBase):
    async def synthesize(self, text: str, voice: str | None = None) -> SynthesizedAudio:
        raw, request_id = await self._post({
            "model": self.model,
            "messages": [{"role": "user", "content": "请使用清晰、自然、专业的中文口试考官语气。"}, {"role": "assistant", "content": text}],
            "audio": {"format": "wav", "voice": voice or "mimo_default"}, "stream": False,
        })
        encoded = raw.get("audio") or raw.get("data") or (((raw.get("choices") or [{}])[0].get("message") or {}).get("audio") or {}).get("data")
        if not isinstance(encoded, str):
            raise ProviderFailure("MiMo TTS response lacks audio data")
        try:
            return SynthesizedAudio(content=base64.b64decode(encoded), mime_type="audio/wav", model=self.model, raw_response=raw, request_id=request_id)
        except ValueError as exc:
            raise ProviderFailure("MiMo TTS returned malformed audio") from exc

    async def transcribe(self, audio: AudioReference):
        raise NotImplementedError("TTS provider cannot transcribe")
