from __future__ import annotations

from typing import Protocol


class VersionedRecord(Protocol):
    status: str


class ImmutablePublishedVersionError(ValueError):
    pass


def assert_version_mutable(record: VersionedRecord) -> None:
    if record.status == "PUBLISHED":
        raise ImmutablePublishedVersionError("Published versions are immutable; create a new draft version")
