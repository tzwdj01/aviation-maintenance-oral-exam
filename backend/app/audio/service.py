from __future__ import annotations

import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.ai.providers.base import AudioReference
from app.audio.signing import sign_media_url
from app.audio.storage import StorageAdapter
from app.audio.validation import validate_audio
from app.core.config import Settings, get_settings
from app.core.enums import AudioPurpose
from app.models.domain import MediaAsset

_MIME_EXTENSION = {"audio/wav": "wav", "audio/mpeg": "mp3", "audio/mp3": "mp3"}


class MediaService:
    """Upload validation, controlled storage and access URL prototype (ARCHITECTURE §3)."""

    def __init__(
        self,
        session: Session,
        storage: StorageAdapter,
        *,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.settings = settings or get_settings()

    def store_audio(
        self,
        audio: AudioReference,
        purpose: AudioPurpose,
        *,
        attempt_id: Any | None = None,
        attempt_item_id: Any | None = None,
        answer_id: Any | None = None,
        retention: dict[str, Any] | None = None,
        storage_key_prefix: str | None = None,
    ) -> MediaAsset:
        metadata = validate_audio(
            audio,
            max_size_bytes=self.settings.media_max_size_bytes,
            allowed_mime_types=self.settings.media_allowed_mime_types,
            max_duration_seconds=self.settings.media_max_duration_seconds,
        )
        prefix = storage_key_prefix or purpose.value.lower()
        extension = _MIME_EXTENSION.get(metadata.mime_type, "bin")
        storage_key = f"{prefix}/{uuid.uuid4()}.{extension}"
        self.storage.store(storage_key, audio.content)
        asset = MediaAsset(
            storage_key=storage_key,
            purpose=purpose.value,
            mime_type=metadata.mime_type,
            codec=metadata.codec,
            sample_rate=metadata.sample_rate,
            channels=metadata.channels,
            duration_ms=metadata.duration_ms,
            size_bytes=metadata.size_bytes,
            sha256=metadata.sha256,
            retention=retention or {},
            attempt_id=attempt_id,
            attempt_item_id=attempt_item_id,
            answer_id=answer_id,
        )
        self.session.add(asset)
        self.session.flush()
        return asset

    def read_audio(self, asset: MediaAsset) -> AudioReference:
        content = self.storage.read(asset.storage_key)
        return AudioReference(
            content=content,
            filename=asset.storage_key.rsplit("/", 1)[-1],
            mime_type=asset.mime_type,
        )

    def access_url(self, asset: MediaAsset, *, ttl_seconds: int | None = None) -> str:
        ttl = ttl_seconds or self.settings.media_access_url_ttl_seconds
        expires_at = int(time.time()) + ttl
        return sign_media_url(asset.storage_key, expires_at, self.settings)
