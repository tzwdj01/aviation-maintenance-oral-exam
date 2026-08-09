from app.ai.providers.base import AudioReference, SynthesizedAudio, TranscriptResult


class FakeSpeechProvider:
    provider_name = "FAKE"

    def __init__(self, transcript: str = "模拟转写") -> None:
        self.transcript = transcript

    async def transcribe(self, audio: AudioReference) -> TranscriptResult:
        return TranscriptResult(text=self.transcript, model="fake-asr-v1", raw_response={"text": self.transcript}, request_id="fake-asr")

    async def synthesize(self, text: str, voice: str | None = None) -> SynthesizedAudio:
        return SynthesizedAudio(content=b"RIFFfake", mime_type="audio/wav", model="fake-tts-v1", raw_response={"text": text}, request_id="fake-tts")
