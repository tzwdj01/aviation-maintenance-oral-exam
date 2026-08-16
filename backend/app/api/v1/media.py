from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audio.signing import verify_media_signature
from app.audio.storage import LocalStorageAdapter
from app.core.config import get_settings
from app.db.session import get_db
from app.models.domain import MediaAsset

router = APIRouter(prefix="/media", tags=["media"])


def get_media_storage() -> LocalStorageAdapter:
    settings = get_settings()
    return LocalStorageAdapter(settings.media_storage_dir)


@router.get("/{storage_key:path}")
def get_media(
    storage_key: str,
    expires: int,
    sig: str,
    db: Session = Depends(get_db),
    storage: LocalStorageAdapter = Depends(get_media_storage),
) -> Response:
    """Serve a stored audio artifact only via a valid, short-lived signed URL."""
    settings = get_settings()
    if int(time.time()) > expires:
        raise HTTPException(status_code=403, detail="media access URL expired")
    if not verify_media_signature(storage_key, expires, sig, settings):
        raise HTTPException(status_code=403, detail="invalid media access signature")
    asset = db.scalar(select(MediaAsset).where(MediaAsset.storage_key == storage_key))
    if not asset:
        raise HTTPException(status_code=404, detail="media asset not found")
    try:
        content = storage.read(storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="media asset content missing") from exc
    return Response(content=content, media_type=asset.mime_type)
