"""Contracts for learner-facing StudyKit capabilities."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LearningReply(BaseModel):
    answer: str
    usage: dict[str, int] = Field(default_factory=dict)


class MaterialAnswerDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=3000)
    citation_ids: list[str] = Field(min_length=1, max_length=4)


class PracticeFeedbackDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correct_points: list[str] = Field(default_factory=list, max_length=4)
    correction: str | None = Field(default=None, max_length=1200)
    next_hint: str = Field(min_length=1, max_length=1000)
    source_pages: list[int] = Field(min_length=1, max_length=12)
