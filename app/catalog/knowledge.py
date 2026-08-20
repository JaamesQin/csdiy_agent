"""Learner-visible course knowledge projected from the reviewed registry."""

from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Any, Protocol

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.catalog.courses import CatalogDataError, CourseCatalogStore


MAX_COURSE_INDEX_CHARACTERS = 64_000
MAX_COURSE_DETAIL_CHARACTERS = 48_000
MAX_RELEVANT_COURSES = 12

_DIRECTION_GROUPS: dict[str, set[str]] = {
    "systems": {
        "systems",
        "operating_systems",
        "architecture",
        "networks",
        "distributed_systems",
        "databases",
        "compilers",
        "parallel_computing",
    },
    "ml_ai": {
        "ml_ai",
        "machine_learning",
        "deep_learning",
        "artificial_intelligence",
        "computer_vision",
        "natural_language_processing",
        "reinforcement_learning",
    },
    "algorithms": {"algorithms", "data_structures", "competitive_programming"},
    "security": {"security", "cryptography"},
    "web_frontend": {"web_frontend", "web", "software_engineering"},
    "web_backend": {"web_backend", "web", "databases", "software_engineering"},
    "theory": {
        "theory",
        "theoretical_computer_science",
        "formal_methods",
        "programming_languages",
        "mathematics",
    },
}

_QUERY_DIRECTION_MARKERS: dict[str, tuple[str, ...]] = {
    "systems": ("系统", "操作系统", "体系结构", "网络", "数据库", "编译", "分布式", "并行"),
    "ml_ai": ("机器学习", "深度学习", "人工智能", "自然语言", "计算机视觉", "强化学习"),
    "algorithms": ("算法", "数据结构", "竞赛"),
    "security": ("安全", "密码学"),
    "web_frontend": ("前端", "frontend", "react", "ui"),
    "web_backend": ("后端", "backend", "web 开发"),
    "theory": ("理论", "形式化", "计算理论", "程序语言"),
}


class CourseKnowledgeIndexEntry(BaseModel):
    """Compact learning-decision metadata for one registry course."""

    model_config = ConfigDict(extra="forbid")

    catalog_id: str
    title: str
    institution: str | None = None
    course_numbers: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    major_direction: str
    secondary_directions: list[str] = Field(default_factory=list)
    introductory_value: int = Field(ge=0, le=5)
    downstream_prerequisite_value: int = Field(ge=0, le=5)
    priority_cohort: str
    public_source_readiness: int = Field(ge=0, le=5)
    notes_public_status: str
    authoring_status: str
    has_selected_offering: bool
    online_ready: bool


class CourseKnowledgeDetail(BaseModel):
    """Sanitized registry detail safe to include in an online model prompt."""

    model_config = ConfigDict(extra="forbid")

    course: CourseKnowledgeIndexEntry
    language_variants: list[str] = Field(default_factory=list)
    navigation_url: str
    official_url: str | None = None
    course_version: str | None = None
    priority_reason: str
    notes_completeness: str
    notes_kind: str
    notes_license_status: str


class CourseKnowledgeStore(Protocol):
    def list_index(self) -> list[CourseKnowledgeIndexEntry]:
        """Return the complete compact registry projection in stable order."""

    def get_detail(self, catalog_id: str) -> CourseKnowledgeDetail | None:
        """Return one sanitized detail record by canonical catalog identity."""

    def relevant_details(
        self,
        query: str,
        *,
        directions: tuple[str, ...] = (),
        preferred_ids: tuple[str, ...] = (),
        limit: int = MAX_RELEVANT_COURSES,
    ) -> list[CourseKnowledgeDetail]:
        """Select prompt details deterministically without semantic model routing."""


class ReviewedCourseKnowledgeStore:
    """Project safe decision metadata from every validated registry target."""

    def __init__(
        self,
        catalog: CourseCatalogStore,
        registry_path: Path | None = None,
    ) -> None:
        root = Path(__file__).resolve().parents[2]
        self._catalog = catalog
        self._registry_path = registry_path or root / "data" / "catalog" / "csdiy-course-registry.yaml"
        self._index: list[CourseKnowledgeIndexEntry] | None = None
        self._details: dict[str, CourseKnowledgeDetail] | None = None

    def list_index(self) -> list[CourseKnowledgeIndexEntry]:
        self._load()
        assert self._index is not None
        return [item.model_copy(deep=True) for item in self._index]

    def get_detail(self, catalog_id: str) -> CourseKnowledgeDetail | None:
        self._load()
        assert self._details is not None
        item = self._details.get(catalog_id)
        return item.model_copy(deep=True) if item is not None else None

    def relevant_details(
        self,
        query: str,
        *,
        directions: tuple[str, ...] = (),
        preferred_ids: tuple[str, ...] = (),
        limit: int = MAX_RELEVANT_COURSES,
    ) -> list[CourseKnowledgeDetail]:
        self._load()
        assert self._index is not None and self._details is not None
        capped = max(1, min(limit, MAX_RELEVANT_COURSES))
        ordered_ids: list[str] = []

        def add(catalog_id: str) -> None:
            if catalog_id in self._details and catalog_id not in ordered_ids:
                ordered_ids.append(catalog_id)

        for catalog_id in preferred_ids:
            add(catalog_id)
        for card in self._catalog.match_explicit(query, limit=5):
            add(card.catalog_id)

        normalized_directions: set[str] = set()
        for direction in directions:
            normalized = _normalize(direction)
            normalized_directions.update(
                _DIRECTION_GROUPS.get(normalized, {normalized})
            )
        lowered_query = query.casefold()
        for direction, markers in _QUERY_DIRECTION_MARKERS.items():
            if any(marker.casefold() in lowered_query for marker in markers):
                normalized_directions.update(_DIRECTION_GROUPS[direction])
        if normalized_directions:
            ranked = sorted(
                self._index,
                key=lambda item: (
                    -int(
                        bool(
                            normalized_directions
                            & {
                                _normalize(item.major_direction),
                                *(_normalize(value) for value in item.secondary_directions),
                            }
                        )
                    ),
                    -item.introductory_value,
                    -item.downstream_prerequisite_value,
                    -item.public_source_readiness,
                    item.title.casefold(),
                    item.catalog_id,
                ),
            )
            for item in ranked:
                if normalized_directions & {
                    _normalize(item.major_direction),
                    *(_normalize(value) for value in item.secondary_directions),
                }:
                    add(item.catalog_id)
        return [self._details[catalog_id].model_copy(deep=True) for catalog_id in ordered_ids[:capped]]

    def _load(self) -> None:
        if self._index is not None:
            return
        try:
            raw = yaml.safe_load(self._registry_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise CatalogDataError("course knowledge registry is unreadable") from exc
        targets = raw.get("course_targets") if isinstance(raw, dict) else None
        if not isinstance(targets, list):
            raise CatalogDataError("course knowledge registry has no course_targets list")

        cards = {card.catalog_id: card for card in self._catalog.list_courses()}
        raw_ids = {
            str(target.get("canonical_course_id"))
            for target in targets
            if isinstance(target, dict) and target.get("canonical_course_id")
        }
        if raw_ids != set(cards):
            raise CatalogDataError("course knowledge identities do not match validated catalog")

        index: list[CourseKnowledgeIndexEntry] = []
        details: dict[str, CourseKnowledgeDetail] = {}
        try:
            for target in targets:
                if not isinstance(target, dict):
                    raise CatalogDataError("course knowledge target is not an object")
                catalog_id = str(target["canonical_course_id"])
                card = cards[catalog_id]
                priority = _required_mapping(target.get("priority"), catalog_id, "priority")
                entry = CourseKnowledgeIndexEntry(
                    catalog_id=catalog_id,
                    title=card.title,
                    institution=card.institution,
                    course_numbers=card.course_numbers,
                    aliases=card.aliases,
                    categories=card.categories,
                    major_direction=_required_text(priority.get("major_direction"), "major_direction"),
                    secondary_directions=_text_list(priority.get("secondary_directions")),
                    introductory_value=_required_int(priority.get("introductory_value"), "introductory_value"),
                    downstream_prerequisite_value=_required_int(
                        priority.get("downstream_prerequisite_value"),
                        "downstream_prerequisite_value",
                    ),
                    priority_cohort=_required_text(priority.get("priority_cohort"), "priority_cohort"),
                    public_source_readiness=_required_int(
                        priority.get("public_source_readiness"), "public_source_readiness"
                    ),
                    notes_public_status=_required_text(
                        priority.get("notes_public_status"), "notes_public_status"
                    ),
                    authoring_status=card.authoring_status,
                    has_selected_offering=isinstance(target.get("selected_offering"), dict),
                    online_ready=card.online_ready,
                )
                detail = CourseKnowledgeDetail(
                    course=entry,
                    language_variants=_text_list(target.get("language_variants")),
                    navigation_url=card.navigation_url,
                    official_url=card.official_url,
                    course_version=card.course_version,
                    priority_reason=_required_text(priority.get("priority_reason"), "priority_reason"),
                    notes_completeness=_required_text(
                        priority.get("notes_completeness"), "notes_completeness"
                    ),
                    notes_kind=_required_text(priority.get("notes_kind"), "notes_kind"),
                    notes_license_status=_required_text(
                        priority.get("notes_license_status"), "notes_license_status"
                    ),
                )
                index.append(entry)
                details[catalog_id] = detail
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise CatalogDataError("course knowledge projection failed validation") from exc

        self._index = sorted(index, key=lambda item: (item.title.casefold(), item.catalog_id))
        self._details = details


def _required_mapping(value: Any, catalog_id: str, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CatalogDataError(f"target {catalog_id} has no {label}")
    return value


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")
    return value.strip()


def _required_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    return value


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, (str, int, float)) for item in value):
        raise ValueError("expected a scalar list")
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize(value: str) -> str:
    return re.sub(r"[^\w]+", "", value.casefold(), flags=re.UNICODE)


def compact_course_index(
    entries: list[CourseKnowledgeIndexEntry],
) -> dict[str, object]:
    """Serialize every identity compactly while retaining field semantics."""

    fields = [
        "catalog_id",
        "title",
        "institution",
        "course_numbers",
        "aliases",
        "major_direction",
        "secondary_directions",
        "introductory_value",
        "downstream_prerequisite_value",
        "priority_cohort",
        "public_source_readiness",
        "authoring_status",
        "online_ready",
    ]
    rows = [
        [
            item.catalog_id,
            item.title,
            item.institution,
            item.course_numbers,
            item.aliases,
            item.major_direction,
            item.secondary_directions,
            item.introductory_value,
            item.downstream_prerequisite_value,
            item.priority_cohort,
            item.public_source_readiness,
            item.authoring_status,
            item.online_ready,
        ]
        for item in entries
    ]
    payload: dict[str, object] = {"fields": fields, "courses": rows}
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(serialized) > MAX_COURSE_INDEX_CHARACTERS:
        raise CatalogDataError("compact course knowledge index exceeds prompt budget")
    return payload


def bounded_course_details(
    details: list[CourseKnowledgeDetail],
) -> list[dict[str, object]]:
    """Return only complete detail records that fit the independent prompt budget."""

    payload: list[dict[str, object]] = []
    characters = 2
    for detail in details[:MAX_RELEVANT_COURSES]:
        item = detail.model_dump(mode="json")
        size = len(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
        if characters + size + 1 > MAX_COURSE_DETAIL_CHARACTERS:
            break
        payload.append(item)
        characters += size + 1
    return payload
