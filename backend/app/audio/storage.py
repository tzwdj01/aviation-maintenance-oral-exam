from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class StorageRef:
    key: str


class StorageAdapter(Protocol):
    """Storage seam for audio artifacts; production stores go through this abstraction."""

    def store(self, key: str, content: bytes) -> StorageRef: ...
    def read(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...


class LocalStorageAdapter:
    """Development-only local filesystem storage (docs/ARCHITECTURE.md §2)."""

    def __init__(self, base_dir: str) -> None:
        self.base_dir = Path(base_dir).resolve()

    def _resolve(self, key: str) -> Path:
        path = (self.base_dir / key).resolve()
        if not path.is_relative_to(self.base_dir):
            raise ValueError("storage key escapes the media root")
        return path

    def store(self, key: str, content: bytes) -> StorageRef:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return StorageRef(key=key)

    def read(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()
