"""Development-only real MiMo speech smoke test (not part of CI).

Usage:
    python -m scripts.smoke_speech

Reads credentials from the environment via `app.core.config.Settings` and never prints the
API key. Performs a TTS synthesis and an ASR round-trip on the synthesized audio, then
reports latency / request IDs / result sizes for the Speech Gate review.
"""

from __future__ import annotations

import asyncio
import sys
import time

from app.ai.providers.base import AudioReference
from app.ai.providers.speech.mimo_asr import MiMoASRProvider
from app.ai.providers.speech.mimo_tts import MiMoTTSProvider
from app.core.config import get_settings


def _key_status() -> str:
    settings = get_settings()
    if settings.mimo_api_key and settings.mimo_api_key.get_secret_value():
        return "CONFIGURED"
    return "NOT_CONFIGURED"


async def run() -> int:
    settings = get_settings()
    print(f"MIMO_API_KEY={_key_status()}")
    if _key_status() != "CONFIGURED":
        print("SMOKE_SKIPPED=credentials not configured; no real provider call performed")
        return 2

    asr = MiMoASRProvider(
        settings.mimo_base_url,
        settings.mimo_api_key.get_secret_value(),
        settings.mimo_asr_model,
        language=settings.mimo_asr_language,
        connect_timeout_seconds=settings.ai_connect_timeout_seconds,
        request_timeout_seconds=settings.ai_request_timeout_seconds,
    )
    tts = MiMoTTSProvider(
        settings.mimo_base_url,
        settings.mimo_api_key.get_secret_value(),
        settings.mimo_tts_model,
        voice=settings.mimo_tts_voice,
        connect_timeout_seconds=settings.ai_connect_timeout_seconds,
        request_timeout_seconds=settings.ai_request_timeout_seconds,
    )

    stem = "请说明在完成维修工作后，放行人员需要核对哪些记录。"
    started = time.monotonic()
    audio = await tts.synthesize(stem)
    tts_latency_ms = int((time.monotonic() - started) * 1000)
    print(f"TTS model={audio.model} request_id={audio.request_id} mime={audio.mime_type} bytes={len(audio.content)} latency_ms={tts_latency_ms}")

    started = time.monotonic()
    transcript = await asr.transcribe(
        AudioReference(content=audio.content, filename="smoke.wav", mime_type=audio.mime_type)
    )
    asr_latency_ms = int((time.monotonic() - started) * 1000)
    print(f"ASR model={transcript.model} request_id={transcript.request_id} latency_ms={asr_latency_ms}")
    print(f"ASR transcript={transcript.text!r}")
    print("SMOKE_RESULT=OK" if transcript.text.strip() else "SMOKE_RESULT=EMPTY_TRANSCRIPT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(run()))
    except Exception as exc:  # noqa: BLE001 - dev tool prints failure reason
        print(f"SMOKE_RESULT=FAILED: {type(exc).__name__}: {exc}")
        sys.exit(1)
