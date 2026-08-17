"""Human-reviewed course-advice sidecars and fit/readiness separation."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agent.contracts import CourseQuery
from app.catalog.contracts import CourseCard


class CourseAdviceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog_id: str
    prerequisites: list[str] | None = None
    difficulty: str | None = None
    weekly_minutes: int | None = Field(default=None, ge=30, le=10080)
    languages: list[str] | None = None
    learning_outcomes: list[str] | None = None
    provenance: list[str] = Field(min_length=1)
    review_status: str

    def model_post_init(self, __context: object) -> None:
        if self.review_status != "approved":
            raise ValueError("course advice metadata must be human-approved")


class CourseRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_id: str
    target_fit_score: int = Field(ge=0)
    online_ready: bool
    reasons: list[str] = Field(default_factory=list)
    unknown_fields: list[str] = Field(default_factory=list)


class CourseAdviceStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._items: dict[str, CourseAdviceMetadata] | None = None

    def get(self, catalog_id: str) -> CourseAdviceMetadata | None:
        item = self._load().get(catalog_id)
        return item.model_copy(deep=True) if item else None

    def rank(
        self, cards: list[CourseCard], query: CourseQuery
    ) -> list[CourseRecommendation]:
        recommendations: list[CourseRecommendation] = []
        for card in cards:
            metadata = self._load().get(card.catalog_id)
            score = 0
            reasons: list[str] = []
            unknown: list[str] = []
            if metadata is None:
                unknown.extend(
                    ["prerequisites", "difficulty", "weekly_minutes", "languages", "learning_outcomes"]
                )
            else:
                if query.languages:
                    if metadata.languages is None:
                        unknown.append("languages")
                    else:
                        overlap = sorted(set(query.languages) & set(metadata.languages))
                        score += len(overlap) * 10
                        if overlap:
                            reasons.append(f"语言匹配：{'、'.join(overlap)}")
                if query.difficulty:
                    if metadata.difficulty is None:
                        unknown.append("difficulty")
                    elif query.difficulty == metadata.difficulty:
                        score += 15
                        reasons.append(f"难度匹配：{metadata.difficulty}")
                if query.max_weekly_minutes is not None:
                    if metadata.weekly_minutes is None:
                        unknown.append("weekly_minutes")
                    elif metadata.weekly_minutes <= query.max_weekly_minutes:
                        score += 10
                        reasons.append("工作量符合本轮上限")
                if query.desired_outcomes:
                    if metadata.learning_outcomes is None:
                        unknown.append("learning_outcomes")
                    else:
                        for outcome in query.desired_outcomes:
                            if any(outcome.casefold() in item.casefold() for item in metadata.learning_outcomes):
                                score += 10
                                reasons.append(f"学习成果匹配：{outcome}")
                if metadata.prerequisites is None:
                    unknown.append("prerequisites")
            recommendations.append(
                CourseRecommendation(
                    catalog_id=card.catalog_id,
                    target_fit_score=score,
                    online_ready=card.online_ready,
                    reasons=list(dict.fromkeys(reasons)),
                    unknown_fields=list(dict.fromkeys(unknown)),
                )
            )
        return sorted(
            recommendations,
            key=lambda item: (-item.target_fit_score, item.catalog_id),
        )

    def _load(self) -> dict[str, CourseAdviceMetadata]:
        if self._items is not None:
            return self._items
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            records = raw.get("courses") if isinstance(raw, dict) else None
            if not isinstance(records, list):
                raise ValueError("course advice sidecar has no courses list")
            items = [CourseAdviceMetadata.model_validate(item) for item in records]
        except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise ValueError("course advice sidecar is invalid") from exc
        if len({item.catalog_id for item in items}) != len(items):
            raise ValueError("course advice sidecar has duplicate catalog IDs")
        self._items = {item.catalog_id: item for item in items}
        return self._items
