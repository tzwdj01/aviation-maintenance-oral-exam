from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AudioMetadata:
    """Validated audio artifact metadata (docs/DATA_MODEL.md §3 `media_assets`)."""

    mime_type: str
    codec: str | None
    sample_rate: int | None
    channels: int | None
    duration_ms: int | None
    size_bytes: int
    sha256: str
