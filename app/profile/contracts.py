"""Learner profile data contracts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ProfileFieldName = Literal[
    "learning_directions",
    "goals",
    "background",
    "weekly_minutes",
    "preferred_explanation_style",
    "active_course",
    "active_unit",
]


class FactStatus(str, Enum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    DECLINED = "declined"


class ProfileFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    user_id: str | None = None
    field_name: ProfileFieldName
    value: Any = None
    status: FactStatus
    confidence: float = Field(ge=0, le=1)
    evidence_excerpt: str | None = None
    course_id: str | None = None
    course_version: str | None = None
    unit_id: str | None = None
    created_at: datetime
    expires_at: datetime | None = None


class LearnerProfile(BaseModel):
    user_id: str | None = None
    facts: list[ProfileFact] = Field(default_factory=list)
    persisted: bool = False

    def confirmed(self, field_name: ProfileFieldName) -> list[ProfileFact]:
        return [
            fact
            for fact in self.facts
            if fact.field_name == field_name and fact.status is FactStatus.CONFIRMED
        ]

    def inferred(self) -> list[ProfileFact]:
        return [fact for fact in self.facts if fact.status is FactStatus.INFERRED]


class ProfileCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_name: ProfileFieldName
    value: Any = None
    status: FactStatus
    confidence: float = Field(ge=0, le=1)
    evidence_quote: str | None = None
    course_id: str | None = None
    course_version: str | None = None
    unit_id: str | None = None


class ProfileObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[ProfileCandidate] = Field(default_factory=list)


class ObservationResult(BaseModel):
    profile: LearnerProfile
    added: list[ProfileFact] = Field(default_factory=list)
    notice: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)
    persistence_error: bool = False
