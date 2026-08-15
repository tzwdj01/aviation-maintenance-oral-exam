import hashlib
import json
from typing import Any

SENSITIVE_KEYS = frozenset({"authorization", "api_key", "apikey", "token", "secret", "password"})


def redact(value: Any) -> Any:
    """Recursively remove credentials before an audit payload is persisted or logged."""
    if isinstance(value, dict):
        return {key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def request_hash(payload: Any) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()
