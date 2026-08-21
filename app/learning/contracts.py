"""Contracts for learner-facing StudyKit capabilities."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LearningReply(BaseModel):
    answer: str
    usage: dict[str, int] = Field(default_factory=dict)
    active_practice_id: str | None = None
    presentation_kind: Literal["original", "structured_rewrite", "grounded_variant"] | None = None
    presentation_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    presentation_fallback_reason: str | None = None


class MaterialClaimDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    provenance: Literal["course_material", "general_knowledge"]
    citation_ids: list[str] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def validate_citations(self) -> "MaterialClaimDraft":
        if self.provenance == "course_material" and not self.citation_ids:
            raise ValueError("course material claims require citations")
        if self.provenance == "general_knowledge" and self.citation_ids:
            raise ValueError("general knowledge cannot claim course citations")
        return self


class MaterialAnswerDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[MaterialClaimDraft] = Field(min_length=1, max_length=8)


class PracticePresentationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    practice_id: str = Field(min_length=1, max_length=300)
    transformation_kind: Literal["structured_rewrite", "grounded_variant"]
    title: str = Field(min_length=1, max_length=300)
    scenario: str | None = Field(default=None, max_length=1200)
    givens: list[str] = Field(default_factory=list, max_length=12)
    question: str = Field(min_length=1, max_length=2400)
    constraints: list[str] = Field(default_factory=list, max_length=12)
    deliverable: str = Field(min_length=1, max_length=1200)
    estimated_minutes: int | None = Field(default=None, ge=1, le=240)
    citation_ids: list[str] = Field(default_factory=list, max_length=16)
    retained_objective_ids: list[str] = Field(default_factory=list, max_length=32)
    retained_requirement_ids: list[str] = Field(default_factory=list, max_length=32)


class PracticeFeedbackDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provenance: Literal["course_material", "general_knowledge"]
    correct_points: list[str] = Field(default_factory=list, max_length=4)
    correction: str | None = Field(default=None, max_length=1200)
    next_hint: str = Field(min_length=1, max_length=1000)
    citation_ids: list[str] = Field(default_factory=list, max_length=16)
