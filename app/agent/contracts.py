"""Typed contracts shared by the online Agent runtime."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class CatalogCourseIdentity(BaseModel):
    """A trusted catalog identity; it does not imply online material access."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog_id: str = Field(min_length=1, max_length=200)
    title: str | None = Field(default=None, max_length=500)


class StudyKitCourseIdentity(BaseModel):
    """An identity resolved exclusively by an online-ready StudyKit store."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    course_id: str = Field(min_length=1, max_length=200)
    course_version: str = Field(min_length=1, max_length=200)
    unit_id: str | None = Field(default=None, max_length=200)

    @classmethod
    def from_context(cls, context: CourseContext) -> "StudyKitCourseIdentity":
        return cls(
            course_id=context.course_id,
            course_version=context.course_version,
            unit_id=context.unit_id,
        )


class CourseQuery(BaseModel):
    """Controlled learner requirements; unknown metadata is never model-filled."""

    model_config = ConfigDict(extra="forbid")

    directions: list[str] = Field(default_factory=list, max_length=8)
    languages: list[str] = Field(default_factory=list, max_length=8)
    difficulty: Literal["introductory", "intermediate", "advanced"] | None = None
    max_weekly_minutes: int | None = Field(default=None, ge=30, le=10080)
    prerequisites: list[str] = Field(default_factory=list, max_length=16)
    desired_outcomes: list[str] = Field(default_factory=list, max_length=16)


class ProvenanceKind(str, Enum):
    COURSE_MATERIAL = "course_material"
    CATALOG_METADATA = "catalog_metadata"
    STATIC_ANALYSIS = "static_analysis"
    GENERAL_KNOWLEDGE = "general_knowledge"


class AnswerClaim(BaseModel):
    """A learner-visible claim with source-specific, mechanically checked provenance."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=12000)
    provenance: ProvenanceKind
    citation_ids: list[str] = Field(default_factory=list, max_length=32)
    catalog_ids: list[str] = Field(default_factory=list, max_length=32)
    diagnostic_ids: list[str] = Field(default_factory=list, max_length=32)
    supported: bool = True

    @model_validator(mode="after")
    def validate_source_binding(self) -> "AnswerClaim":
        required = {
            ProvenanceKind.COURSE_MATERIAL: self.citation_ids,
            ProvenanceKind.CATALOG_METADATA: self.catalog_ids,
            ProvenanceKind.STATIC_ANALYSIS: self.diagnostic_ids,
        }
        identifiers = required.get(self.provenance)
        if identifiers is not None and not identifiers:
            raise ValueError(f"{self.provenance.value} claims require source identifiers")
        if self.provenance is ProvenanceKind.GENERAL_KNOWLEDGE and any(
            (self.citation_ids, self.catalog_ids, self.diagnostic_ids)
        ):
            raise ValueError("general_knowledge claims cannot assert trusted source identifiers")
        return self


class PlannedTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    capability_id: CapabilityId
    objective: str = Field(min_length=1, max_length=1000)
    depends_on: list[str] = Field(default_factory=list, max_length=8)
    parameters: dict[str, Any] = Field(default_factory=dict)
    required_context: list[str] = Field(default_factory=list, max_length=16)
    self_statement: bool = False


class TaskPlan(BaseModel):
    """A bounded, acyclic plan produced from the complete conversation."""

    model_config = ConfigDict(extra="forbid")

    user_goal: str = Field(min_length=1, max_length=2000)
    tasks: list[PlannedTask] = Field(min_length=1, max_length=8)
    course_mentions: list[str] = Field(default_factory=list, max_length=16)
    missing_context: list[str] = Field(default_factory=list, max_length=16)
    clarifying_questions: list[str] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def validate_dag(self) -> "TaskPlan":
        ids = [task.task_id for task in self.tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("task IDs must be unique")
        capabilities = [task.capability_id for task in self.tasks]
        if len(capabilities) != len(set(capabilities)):
            raise ValueError("each capability may appear at most once per task plan")
        known = set(ids)
        graph: dict[str, list[str]] = {}
        for task in self.tasks:
            if task.task_id in task.depends_on:
                raise ValueError("a task cannot depend on itself")
            unknown = set(task.depends_on) - known
            if unknown:
                raise ValueError(f"unknown task dependencies: {sorted(unknown)}")
            graph[task.task_id] = task.depends_on
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visiting:
                raise ValueError("task dependencies must be acyclic")
            if task_id in visited:
                return
            visiting.add(task_id)
            for dependency in graph[task_id]:
                visit(dependency)
            visiting.remove(task_id)
            visited.add(task_id)

        for task_id in ids:
            visit(task_id)
        return self

    def ordered_tasks(self) -> list[PlannedTask]:
        remaining = {task.task_id: task for task in self.tasks}
        completed: set[str] = set()
        ordered: list[PlannedTask] = []
        while remaining:
            ready = [
                task
                for task in self.tasks
                if task.task_id in remaining and set(task.depends_on) <= completed
            ]
            for task in ready:
                ordered.append(task)
                completed.add(task.task_id)
                remaining.pop(task.task_id)
        return ordered


class TaskStatus(str, Enum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class TaskExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    capability_id: CapabilityId
    status: TaskStatus
    answer: str | None = None
    missing_context: list[str] = Field(default_factory=list)
    claims: list[AnswerClaim] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)


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
    coursepilot_context: str | None = None
