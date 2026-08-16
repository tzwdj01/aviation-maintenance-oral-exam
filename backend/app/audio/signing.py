from __future__ import annotations

import hashlib
import hmac
import secrets
from urllib.parse import quote

from app.core.config import Settings

# Dev-only secret so signed URLs work without explicit MEDIA_URL_SECRET configuration.
# Production must set MEDIA_URL_SECRET via environment/secret manager (docs/SECURITY.md).
_EPHEMERAL_DEV_SECRET = secrets.token_hex(16)


def _secret(settings: Settings) -> str:
    if settings.media_url_secret and settings.media_url_secret.get_secret_value():
        return settings.media_url_secret.get_secret_value()
    return _EPHEMERAL_DEV_SECRET


def _signature(storage_key: str, expires_at: int, settings: Settings) -> str:
    message = f"{storage_key}:{expires_at}".encode()
    return hmac.new(_secret(settings).encode("utf-8"), message, hashlib.sha256).hexdigest()


def sign_media_url(storage_key: str, expires_at: int, settings: Settings) -> str:
    """Build a short-lived, signed media access URL (controlled access prototype)."""
    encoded_key = quote(storage_key, safe="/")
    return f"/api/v1/media/{encoded_key}?expires={expires_at}&sig={_signature(storage_key, expires_at, settings)}"


def verify_media_signature(storage_key: str, expires_at: int, sig: str, settings: Settings) -> bool:
    expected = _signature(storage_key, expires_at, settings)
    return hmac.compare_digest(expected, sig)
