import hashlib
import json
import re
from typing import Any

SENSITIVE_KEYS = frozenset({"authorization", "api_key", "apikey", "token", "secret", "password"})

# Credential-shaped tokens that must never reach audit artifacts even when they appear
# inside free-text (e.g. an error message). Key-based redaction handles structured
# payloads; these patterns are defense-in-depth for strings.
_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}\b", re.IGNORECASE),
    re.compile(r"\b(?:api[_-]?key|apikey|access[_-]?token|secret|password)\s*[:=]\s*[^\s,}\]]{6,}", re.IGNORECASE),
)


def redact(value: Any) -> Any:
    """Recursively remove credentials before an audit payload is persisted or logged.

    Sensitive dict keys are replaced wholesale; credential-shaped tokens inside free text
    (``sk-...``, ``Bearer ...``, ``api_key=...``) are scrubbed as well.
    """
    if isinstance(value, dict):
        return {key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        for pattern in _SECRET_PATTERNS:
            value = pattern.sub("[REDACTED]", value)
        return value
    return value


def request_hash(payload: Any) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()
