from __future__ import annotations

import io
import wave

from app.ai.providers.base import AudioReference, SynthesizedAudio, TranscriptResult


class FakeSpeechProvider:
    provider_name = "FAKE"

    def __init__(self, transcript: str = "模拟转写") -> None:
        self.transcript = transcript

    @staticmethod
    def _wav_bytes() -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            wav.writeframes(b"\x00\x00" * 8000)
        return buffer.getvalue()

    async def transcribe(self, audio: AudioReference) -> TranscriptResult:
        return TranscriptResult(text=self.transcript, model="fake-asr-v1", raw_response={"text": self.transcript}, request_id="fake-asr")

    async def synthesize(self, text: str, voice: str | None = None) -> SynthesizedAudio:
        return SynthesizedAudio(content=self._wav_bytes(), mime_type="audio/wav", model="fake-tts-v1", raw_response={"text": text}, request_id="fake-tts")
