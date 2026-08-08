"""Code tutor input, context, and result contracts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.agent.contracts import CourseContext


class StaticDiagnostic(BaseModel):
    code: str
    message: str
    line: int | None = None
    column: int | None = None


class TutorCitation(BaseModel):
    citation_id: str
    source_id: str
    page: int
    label: str


class CodeTutorContext(BaseModel):
    course_context: CourseContext | None = None
    language: str | None = None
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
    diagnostic_hypotheses: list[str] = Field(default_factory=list)
    next_checks: list[str] = Field(default_factory=list)
    next_attempt: str
    citation_ids: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)


class TutorResult(BaseModel):
    answer: str
    citations: list[TutorCitation] = Field(default_factory=list)
    diagnostics: list[StaticDiagnostic] = Field(default_factory=list)
    diagnostic_hypotheses: list[str] = Field(default_factory=list)
    next_checks: list[str] = Field(default_factory=list)
    next_attempt: str | None = None
    ran_code: bool = False
    safety_notes: list[str] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)
