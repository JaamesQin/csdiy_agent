"""Data contracts for local StudyKit generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GenerationStage(str, Enum):
    """Ordered pipeline stages."""

    EVIDENCE = "evidence"
    CONTENT = "content"
    PRACTICE = "practice"
    AUDIT = "audit"
    ASSEMBLE = "assemble"


class GenerationStatus(str, Enum):
    """Terminal state of one generation attempt."""

    SUCCEEDED = "succeeded"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INVALID_INPUT = "invalid_input"
    FAILED_VALIDATION = "failed_validation"
    MODEL_ERROR = "model_error"


@dataclass(frozen=True)
class GenerationRequest:
    """Trusted course context and source metadata for one unit."""

    course_id: str | None
    course_version: str | None
    unit_id: str
    included_sources: tuple[dict[str, Any], ...]
    unit_title: str | None = None
    material_set_id: str | None = None
    language: str = "zh-CN"
    target_minutes: int = 180

    def __post_init__(self) -> None:
        if not self.unit_id.strip():
            raise ValueError("unit_id must not be empty")
        if not self.included_sources:
            raise ValueError("included_sources must not be empty")
        if self.unit_title is not None and not self.unit_title.strip():
            raise ValueError("unit_title must not be empty when provided")
        if self.target_minutes <= 0:
            raise ValueError("target_minutes must be positive")

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "course_id": self.course_id,
            "course_version": self.course_version,
            "unit_id": self.unit_id,
            "unit_title": self.unit_title,
            "material_set_id": self.material_set_id,
            "language": self.language,
            "target_minutes": self.target_minutes,
            "included_sources": list(self.included_sources),
        }


@dataclass(frozen=True)
class GenerationIssue:
    """Machine-readable generation or validation problem."""

    stage: str
    code: str
    message: str
    location: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "stage": self.stage,
            "code": self.code,
            "message": self.message,
        }
        if self.location is not None:
            result["location"] = self.location
        return result


@dataclass(frozen=True)
class StageResult:
    """Observable result for one pipeline stage."""

    stage: GenerationStage
    status: str
    attempts: int = 0
    reused: bool = False
    issues: tuple[GenerationIssue, ...] = ()
    model_info: tuple[dict[str, Any], ...] = ()
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "status": self.status,
            "attempts": self.attempts,
            "reused": self.reused,
            "issues": [issue.to_dict() for issue in self.issues],
            "model_calls": list(self.model_info),
            "duration_seconds": self.duration_seconds,
        }


@dataclass(frozen=True)
class GenerationResult:
    """Final output of StudyKitGenerator."""

    status: GenerationStatus
    studykit: dict[str, Any] | None
    issues: tuple[GenerationIssue, ...]
    used_chunk_ids: tuple[str, ...]
    attempts: int
    prompt_version: str
    model_info: dict[str, Any] = field(default_factory=dict)
    stages: tuple[StageResult, ...] = ()
    failed_stage: GenerationStage | None = None

    @property
    def succeeded(self) -> bool:
        return self.status is GenerationStatus.SUCCEEDED

    def validation_report(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "attempts": self.attempts,
            "prompt_version": self.prompt_version,
            "used_chunk_ids": list(self.used_chunk_ids),
            "issues": [issue.to_dict() for issue in self.issues],
            "model": self.model_info,
            "failed_stage": (
                self.failed_stage.value if self.failed_stage is not None else None
            ),
            "stages": [stage.to_dict() for stage in self.stages],
        }
