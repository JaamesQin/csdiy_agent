"""Typed contracts shared by the online Agent runtime."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class CapabilityId(str, Enum):
    PROFILE_ANALYSIS = "profile_analysis"
    CODE_TUTORING = "code_tutoring"
    COURSE_NAVIGATION = "course_navigation"
    STUDYKIT_LOOKUP = "studykit_lookup"
    MATERIAL_QUESTION = "material_question"
    CONCEPT_EXPLANATION = "concept_explanation"
    PRACTICE_SELECTION = "practice_selection"
    PRACTICE_FEEDBACK = "practice_feedback"
    LEARNING_REVIEW = "learning_review"
    GENERATION_STATUS = "generation_status"


class Intent(str, Enum):
    COURSE_NAVIGATION = "course_navigation"
    STUDYKIT_LOOKUP = "studykit_lookup"
    MATERIAL_QUESTION = "material_question"
    CONCEPT_EXPLANATION = "concept_explanation"
    PRACTICE_SELECTION = "practice_selection"
    PRACTICE_FEEDBACK = "practice_feedback"
    CODE_TUTORING = "code_tutoring"
    PROFILE_ANALYSIS = "profile_analysis"
    LEARNING_REVIEW = "learning_review"
    GENERATION_STATUS = "generation_status"
    ADMIN_GENERATE_STUDYKIT = "admin_generate_studykit"
    CAPABILITY_HELP = "capability_help"
    FALLBACK_CLARIFICATION = "fallback_clarification"


class CourseContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: str
    course_version: str
    unit_id: str | None = None
    title: str | None = None


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Intent
    confidence: float = Field(ge=0, le=1)
    course_context: CourseContext | None = None
    capability_id: CapabilityId | None = None
    required_context: list[str] = Field(default_factory=list)
    clarifying_question: str | None = None
    reason: str | None = None


class RouteOutcome(BaseModel):
    decision: RouteDecision
    usage: dict[str, int] = Field(default_factory=dict)


class AgentReply(BaseModel):
    answer: str
    usage: dict[str, int] = Field(default_factory=dict)
