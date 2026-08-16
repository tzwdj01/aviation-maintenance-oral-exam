from __future__ import annotations

import hashlib
import io
import wave

from app.ai.providers.base import AudioReference
from app.audio.metadata import AudioMetadata

_WAV_MIME = {"audio/wav", "audio/x-wav", "audio/wave"}
_MP3_MIME = {"audio/mpeg", "audio/mp3"}


class AudioValidationError(ValueError):
    """Raised when an uploaded audio artifact is invalid; providers are never called."""


def _normalize_mime(mime_type: str) -> str:
    lowered = (mime_type or "").lower().strip()
    if lowered in _WAV_MIME:
        return "audio/wav"
    if lowered in _MP3_MIME:
        return "audio/mpeg"
    return lowered


def validate_audio(
    audio: AudioReference,
    *,
    max_size_bytes: int,
    allowed_mime_types: list[str],
    max_duration_seconds: int,
) -> AudioMetadata:
    """Validate an audio reference before it is stored or sent to a provider.

    Corrupt or unsupported files raise `AudioValidationError` so damaged input never
    reaches a vendor. WAV metadata is read with the stdlib `wave` module; MP3 is checked
    for a valid frame/ID3 header (duration parsing would require ffmpeg, which is out of
    scope for this Sprint — size and MIME still bound it).
    """
    if not audio.content:
        raise AudioValidationError("audio content is empty")
    mime_type = _normalize_mime(audio.mime_type)
    allowed = {_normalize_mime(m) for m in allowed_mime_types}
    if mime_type not in allowed:
        raise AudioValidationError(f"unsupported audio mime type: {audio.mime_type}")
    if len(audio.content) > max_size_bytes:
        raise AudioValidationError(
            f"audio exceeds maximum size of {max_size_bytes} bytes"
        )

    codec: str | None = None
    sample_rate: int | None = None
    channels: int | None = None
    duration_ms: int | None = None

    if mime_type == "audio/wav":
        try:
            with wave.open(io.BytesIO(audio.content), "rb") as wav:
                sample_rate = wav.getframerate()
                channels = wav.getnchannels()
                nframes = wav.getnframes()
                codec = "pcm"
                duration_ms = int(nframes / sample_rate * 1000) if sample_rate else None
        except (wave.Error, EOFError) as exc:
            raise AudioValidationError("wav audio is not readable") from exc
    else:  # audio/mpeg
        header = audio.content[:4]
        is_id3 = header.startswith(b"ID3")
        is_frame = len(audio.content) >= 2 and audio.content[0] == 0xFF and (audio.content[1] & 0xE0) == 0xE0
        if not (is_id3 or is_frame):
            raise AudioValidationError("mp3 audio header is not readable")
        codec = "mp3"

    if duration_ms is not None and duration_ms > max_duration_seconds * 1000:
        raise AudioValidationError(
            f"audio exceeds maximum duration of {max_duration_seconds} seconds"
        )
    return AudioMetadata(
        mime_type=mime_type,
        codec=codec,
        sample_rate=sample_rate,
        channels=channels,
        duration_ms=duration_ms,
        size_bytes=len(audio.content),
        sha256=hashlib.sha256(audio.content).hexdigest(),
    )
