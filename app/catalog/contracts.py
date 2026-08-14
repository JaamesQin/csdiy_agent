"""Typed public contracts for the read-only course catalog."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ReadyStudyKitSummary(BaseModel):
    """Public identity and display metadata for one online-ready StudyKit."""

    model_config = ConfigDict(extra="forbid")

    course_id: str
    course_version: str
    unit_id: str
    title: str
    estimated_study_time_minutes: int | None = Field(default=None, ge=1)
    official_url: str | None = None


class CourseCard(BaseModel):
    """One validated CSDIY catalog target with clearly separated readiness states."""

    model_config = ConfigDict(extra="forbid")

    catalog_id: str
    title: str
    institution: str | None = None
    course_numbers: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    catalog_review_status: str
    authoring_status: str
    navigation_url: str
    official_url: str | None = None
    manifest_course_id: str | None = None
    course_version: str | None = None
    online_studykits: list[ReadyStudyKitSummary] = Field(default_factory=list)

    @property
    def online_ready(self) -> bool:
        return bool(self.online_studykits)
