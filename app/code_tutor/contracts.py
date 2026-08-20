"""Code tutor input, context, and result contracts."""

from __future__ import annotations

import hashlib
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agent.contracts import CodeTutorMode, CourseContext


class CodeTutorRequest(BaseModel):
    """Normalized operation metadata passed from understanding to the tutor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: CodeTutorMode = CodeTutorMode.DIAGNOSE
    target_language: str | None = Field(default=None, max_length=100)
    language_inferred: bool = False
    references_existing_code: bool = False


class TutorCodeBlock(BaseModel):
    """A bounded model-produced code block; it is never executed or persisted."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["example", "repair", "refactor", "tests"]
    language: str = Field(min_length=1, max_length=64)
    filename: str | None = Field(default=None, max_length=200)
    code: str = Field(min_length=1, max_length=20000)
    explanation: str = Field(default="", max_length=4000)
    expected_behavior: str = Field(default="", max_length=4000)


class StaticDiagnostic(BaseModel):
    code: str
    message: str
    line: int | None = None
    column: int | None = None
    end_line: int | None = None
    artifact_id: str | None = None


class CodeArtifact(BaseModel):
    """Ephemeral code identity; context tokens retain only its ID and digest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: str
    version: int = Field(default=1, ge=1)
    language: str | None = None
    filename: str | None = None
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    line_count: int = Field(ge=0)

    @classmethod
    def create(
        cls,
        code: str,
        *,
        language: str | None,
        filename: str | None = None,
        previous: "CodeArtifact | None" = None,
    ) -> "CodeArtifact":
        digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
        if previous is not None and previous.content_sha256 == digest:
            return previous
        return cls(
            artifact_id=f"code-{uuid.uuid4().hex}",
            version=(previous.version + 1 if previous is not None else 1),
            language=language,
            filename=filename,
            content_sha256=digest,
            line_count=len(code.splitlines()),
        )


class TutorHypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    artifact_id: str
    language: str | None = None
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    support_id: str
    verification_step: str
    pending_verification: bool = False


class TutorCitation(BaseModel):
    citation_id: str
    source_id: str
    page: int
    label: str


class CodeTutorContext(BaseModel):
    mode: CodeTutorMode = CodeTutorMode.DIAGNOSE
    course_context: CourseContext | None = None
    language: str | None = None
    target_language: str | None = None
    language_display_name: str | None = None
    deterministic_parser_used: bool = False
    code: str
    error_text: str | None = None
    question: str
    learning_objectives: list[str] = Field(default_factory=list)
    concepts: list[dict[str, object]] = Field(default_factory=list)
    practice: dict[str, object] | None = None
    allowed_citations: list[TutorCitation] = Field(default_factory=list)
    learner_constraints: dict[str, object] = Field(default_factory=dict)


class TutorDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation: str
    code_blocks: list[TutorCodeBlock] = Field(default_factory=list, max_length=3)
    diagnostic_hypotheses: list[str] = Field(default_factory=list)
    next_checks: list[str] = Field(default_factory=list)
    next_attempt: str
    citation_ids: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)


class TutorResult(BaseModel):
    mode: CodeTutorMode = CodeTutorMode.DIAGNOSE
    answer: str
    code_blocks: list[TutorCodeBlock] = Field(default_factory=list, max_length=3)
    citations: list[TutorCitation] = Field(default_factory=list)
    diagnostics: list[StaticDiagnostic] = Field(default_factory=list)
    diagnostic_hypotheses: list[str] = Field(default_factory=list)
    next_checks: list[str] = Field(default_factory=list)
    next_attempt: str | None = None
    ran_code: bool = False
    safety_notes: list[str] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)
    artifact: CodeArtifact | None = None
    bound_hypotheses: list[TutorHypothesis] = Field(default_factory=list, max_length=3)
