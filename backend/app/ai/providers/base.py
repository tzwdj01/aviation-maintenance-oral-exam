from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar

import httpx
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class EvaluationRequest(Generic[T]):
    task_type: str
    system_prompt: str
    candidate_text: str
    rubric_snapshot: dict[str, Any]
    output_type: type[T]
    prompt_version: str
    # Trusted evaluation context (Sprint 1C): these fields are part of the shared
    # TRUSTED_EVALUATION_CONTEXT sent to every provider, never merged into the
    # UNTRUSTED_CANDIDATE_DATA boundary.
    question_text: str = ""
    critical_error_rules: tuple[dict[str, Any], ...] = ()
    prior_analysis: dict[str, Any] | None = None


@dataclass(frozen=True)
class ProviderResponse(Generic[T]):
    value: T
    model: str
    request_id: str | None
    raw_response: dict[str, Any]


@dataclass(frozen=True)
class AudioReference:
    content: bytes
    filename: str
    mime_type: str


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    model: str
    raw_response: dict[str, Any]
    request_id: str | None = None


@dataclass(frozen=True)
class SynthesizedAudio:
    content: bytes
    mime_type: str
    model: str
    raw_response: dict[str, Any]
    request_id: str | None = None


class ProviderFailureKind:
    """Retry classification for provider failures (docs/providers/mimo-speech.md §4/§5)."""

    TEMPORARY = "TEMPORARY"
    PERMANENT = "PERMANENT"


class ProviderFailure(RuntimeError):
    """Provider call failure surfaced to the job/state service.

    The registry never falls back to another provider (ADR-0005). `kind` drives the retry
    policy: TEMPORARY failures may be retried with backoff, PERMANENT failures fail fast.
    `code` carries a stable error code for audit and error mapping.
    """

    def __init__(
        self,
        message: str,
        *,
        kind: str = ProviderFailureKind.PERMANENT,
        code: str | None = None,
        status_code: int | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.code = code
        self.status_code = status_code
        self.request_id = request_id


def map_provider_error(exc: Exception, *, request_id: str | None = None) -> ProviderFailure:
    """Normalize transport/HTTP failures into a classified ProviderFailure.

    Mapping follows docs/providers/mimo-speech.md §5: auth and schema errors are permanent
    (fast-fail), while timeouts, network errors and 5xx are temporary (retryable).
    """
    if isinstance(exc, ProviderFailure):
        return exc
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        status = response.status_code
        rid = request_id or response.headers.get("x-request-id") or response.headers.get("request-id")
        permanent = status in {400, 401, 403, 422}
        return ProviderFailure(
            f"provider http error {status}",
            kind=ProviderFailureKind.PERMANENT if permanent else ProviderFailureKind.TEMPORARY,
            code="HTTP_ERROR",
            status_code=status,
            request_id=rid,
        )
    if isinstance(exc, httpx.TimeoutException):
        return ProviderFailure(
            "provider timeout",
            kind=ProviderFailureKind.TEMPORARY,
            code="TIMEOUT",
            request_id=request_id,
        )
    if isinstance(exc, httpx.HTTPError):
        return ProviderFailure(
            f"provider network error: {exc}",
            kind=ProviderFailureKind.TEMPORARY,
            code="NETWORK_ERROR",
            request_id=request_id,
        )
    return ProviderFailure(
        f"provider failure: {exc}",
        kind=ProviderFailureKind.PERMANENT,
        code="UNKNOWN_ERROR",
        request_id=request_id,
    )


class EvaluationProvider(Protocol):
    provider_name: str
    model: str

    async def evaluate_coverage(self, request: EvaluationRequest[Any]) -> ProviderResponse[Any]: ...
    async def detect_critical_errors(self, request: EvaluationRequest[Any]) -> ProviderResponse[Any]: ...
    async def evaluate_quality_risk(self, request: EvaluationRequest[Any]) -> ProviderResponse[Any]: ...
    async def decide_follow_up(self, request: EvaluationRequest[Any]) -> ProviderResponse[Any]: ...
    async def final_assessment(self, request: EvaluationRequest[Any]) -> ProviderResponse[Any]: ...


class SpeechProvider(Protocol):
    provider_name: str
    async def transcribe(self, audio: AudioReference) -> TranscriptResult: ...
    async def synthesize(self, text: str, voice: str | None = None) -> SynthesizedAudio: ...
