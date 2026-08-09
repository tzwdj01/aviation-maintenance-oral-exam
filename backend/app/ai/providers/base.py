from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar

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


class ProviderFailure(RuntimeError):
    """Failure is surfaced to the job/state service; the registry never falls back to another provider."""


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
