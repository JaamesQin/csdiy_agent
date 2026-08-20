"""Validated, read-only access to the tracked CSDIY course registry."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import yaml
from pydantic import ValidationError

from app.catalog.contracts import CourseCard
from app.catalog.studykits import StudyKitStore


class CatalogDataError(RuntimeError):
    """Raised when tracked catalog data cannot be trusted for online use."""


class CourseCatalogStore(Protocol):
    def list_courses(self) -> list[CourseCard]:
        """Return every validated course target in stable order."""

    def get(self, catalog_id: str) -> CourseCard | None:
        """Return one catalog target by its catalog identity."""

    def search(
        self,
        query: str,
        *,
        directions: tuple[str, ...] = (),
        limit: int = 5,
    ) -> list[CourseCard]:
        """Return a deterministic, readiness-aware catalog ranking."""

    def match_explicit(self, query: str, *, limit: int = 5) -> list[CourseCard]:
        """Match explicit course numbers, IDs, titles, or aliases."""


_AUTHORING_STATES = {
    "discovered",
    "classified",
    "researching_offering",
    "offering_selected",
    "sources_inventoried",
    "downloaded",
    "prepared",
    "chunked",
    "authoring",
    "audited",
    "validated",
    "complete",
    "blocked_no_public_evidence",
    "blocked_access",
    "failed_recoverable",
}

_DIRECTION_MARKERS: dict[str, tuple[str, ...]] = {
    "systems": (
        "操作系统",
        "体系结构",
        "计算机系统",
        "并行",
        "分布式",
        "计算机网络",
        "编译原理",
        "数据库系统",
    ),
    "ml_ai": ("人工智能", "机器学习", "深度学习", "自然语言", "计算机视觉", "强化学习"),
    "algorithms": ("数据结构", "算法", "离散数学", "概率"),
    "security": ("安全", "密码学"),
    "web_frontend": ("web", "前端", "ui", "react"),
    "web_backend": ("web", "后端", "数据库", "软件工程"),
    "theory": ("理论", "形式化", "程序语言", "算法", "数学"),
}


class ReviewedCourseCatalogStore:
    """Load catalog targets and trusted Manifest metadata from tracked YAML."""

    def __init__(
        self,
        studykits: StudyKitStore,
        registry_path: Path | None = None,
        repository_root: Path | None = None,
    ) -> None:
        root = repository_root or Path(__file__).resolve().parents[2]
        self._root = root.resolve()
        self._registry_path = registry_path or root / "data" / "catalog" / "csdiy-course-registry.yaml"
        self._studykits = studykits
        self._courses: list[CourseCard] | None = None

    def list_courses(self) -> list[CourseCard]:
        return [item.model_copy(deep=True) for item in self._load()]

    def get(self, catalog_id: str) -> CourseCard | None:
        return next(
            (item.model_copy(deep=True) for item in self._load() if item.catalog_id == catalog_id),
            None,
        )

    def match_explicit(self, query: str, *, limit: int = 5) -> list[CourseCard]:
        normalized_query = _normalize(query)
        if not normalized_query:
            return []
        scored: list[tuple[int, CourseCard]] = []
        for card in self._load():
            score = self._explicit_score(card, normalized_query)
            if score:
                scored.append((score, card))
        return [
            item.model_copy(deep=True)
            for _, item in sorted(
                scored,
                key=lambda pair: (-pair[0], pair[1].title.casefold(), pair[1].catalog_id),
            )[: max(1, min(limit, 5))]
        ]

    def search(
        self,
        query: str,
        *,
        directions: tuple[str, ...] = (),
        limit: int = 5,
    ) -> list[CourseCard]:
        normalized_query = _normalize(query)
        scored: list[tuple[int, CourseCard]] = []
        for card in self._load():
            explicit = self._explicit_score(card, normalized_query)
            direction = self._direction_score(card, directions, query)
            if normalized_query and not directions and not explicit and not direction:
                continue
            readiness = 30 if card.online_ready else 0
            readiness += 10 if card.manifest_course_id else 0
            readiness += {
                "complete": 8,
                "validated": 7,
                "audited": 6,
                "authoring": 5,
                "chunked": 4,
                "prepared": 3,
                "sources_inventoried": 2,
            }.get(card.authoring_status, 0)
            scored.append((explicit + direction + readiness, card))
        return [
            item.model_copy(deep=True)
            for _, item in sorted(
                scored,
                key=lambda pair: (-pair[0], pair[1].title.casefold(), pair[1].catalog_id),
            )[: max(1, min(limit, 5))]
        ]

    def _load(self) -> list[CourseCard]:
        if self._courses is not None:
            return self._courses
        try:
            raw = yaml.safe_load(self._registry_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise CatalogDataError("course registry is unreadable") from exc
        if not isinstance(raw, dict) or not isinstance(raw.get("course_targets"), list):
            raise CatalogDataError("course registry has no course_targets list")

        seen: set[str] = set()
        courses: list[CourseCard] = []
        for index, target in enumerate(raw["course_targets"]):
            if not isinstance(target, dict):
                raise CatalogDataError(f"course target {index} is not an object")
            card = self._parse_target(target, index)
            if card.catalog_id in seen:
                raise CatalogDataError(f"duplicate catalog id: {card.catalog_id}")
            seen.add(card.catalog_id)
            courses.append(card)
        if not courses:
            raise CatalogDataError("course registry contains no validated course targets")
        self._courses = sorted(courses, key=lambda item: (item.title.casefold(), item.catalog_id))
        return self._courses

    def _parse_target(self, target: dict[str, Any], index: int) -> CourseCard:
        catalog_id = _required_text(target.get("canonical_course_id"), f"target {index} id")
        title = _required_text(target.get("title"), f"target {catalog_id} title")
        state = _required_text(target.get("state"), f"target {catalog_id} state")
        if state not in _AUTHORING_STATES:
            raise CatalogDataError(f"target {catalog_id} has unknown authoring state")
        audit = target.get("audit")
        if not isinstance(audit, dict):
            raise CatalogDataError(f"target {catalog_id} has no audit record")
        review_status = _required_text(
            audit.get("classification"), f"target {catalog_id} classification audit"
        )
        provenance = target.get("guide_page_provenance")
        if not isinstance(provenance, list) or not provenance or not isinstance(provenance[0], dict):
            raise CatalogDataError(f"target {catalog_id} has no guide provenance")
        navigation_url = _validated_url(
            provenance[0].get("public_page_url"),
            f"target {catalog_id} navigation URL",
            required_host="csdiy.wiki",
        )
        categories = sorted(
            {
                str(item.get("leaf_key", "")).split("::", 1)[0].strip()
                for item in provenance
                if isinstance(item, dict) and str(item.get("leaf_key", "")).split("::", 1)[0].strip()
            }
        )
        if not categories:
            raise CatalogDataError(f"target {catalog_id} has no validated course category")
        numbers = _string_list(target.get("course_numbers"), f"target {catalog_id} numbers")
        aliases = _string_list(target.get("aliases"), f"target {catalog_id} aliases")
        institution = target.get("institution")
        if institution is not None and not isinstance(institution, str):
            raise CatalogDataError(f"target {catalog_id} institution must be text or null")

        manifest_path = target.get("manifest_path")
        coverage = target.get("coverage")
        if manifest_path is None and isinstance(coverage, dict):
            manifest_path = coverage.get("manifest_path")
        manifest_course_id: str | None = None
        course_version: str | None = None
        official_url: str | None = None
        online = []
        if manifest_path:
            manifest = self._load_manifest(str(manifest_path), catalog_id)
            if not _manifest_matches_target(manifest, target):
                raise CatalogDataError(
                    f"target {catalog_id} does not match its referenced manifest"
                )
            manifest_course_id = _required_text(
                manifest.get("course_id"), f"target {catalog_id} manifest course_id"
            )
            course_version = _required_text(
                manifest.get("course_version"), f"target {catalog_id} manifest course_version"
            )
            official_url = _validated_url(
                manifest.get("official_url"), f"target {catalog_id} official URL"
            )
            online = self._studykits.list_ready(
                course_id=manifest_course_id,
                course_version=course_version,
            )

        try:
            return CourseCard(
                catalog_id=catalog_id,
                title=title,
                institution=(
                    institution.strip()
                    if isinstance(institution, str) and institution.strip()
                    else None
                ),
                course_numbers=numbers,
                aliases=aliases,
                categories=categories,
                catalog_review_status=review_status,
                authoring_status=state,
                navigation_url=navigation_url,
                official_url=official_url,
                manifest_course_id=manifest_course_id,
                course_version=course_version,
                online_studykits=online,
            )
        except ValidationError as exc:
            raise CatalogDataError(f"target {catalog_id} failed typed validation") from exc

    def _load_manifest(self, relative_path: str, catalog_id: str) -> dict[str, Any]:
        path = (self._root / relative_path).resolve()
        allowed_root = (self._root / "data" / "manifests").resolve()
        if allowed_root not in path.parents or path.suffix not in {".yaml", ".yml"}:
            raise CatalogDataError(f"target {catalog_id} references an unsafe manifest path")
        try:
            manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise CatalogDataError(f"target {catalog_id} manifest is unreadable") from exc
        if not isinstance(manifest, dict):
            raise CatalogDataError(f"target {catalog_id} manifest is not an object")
        return manifest

    @staticmethod
    def _explicit_score(card: CourseCard, normalized_query: str) -> int:
        if not normalized_query:
            return 0
        identities = [card.catalog_id, card.title, *card.aliases, *card.course_numbers]
        scores: list[int] = []
        for identity in identities:
            normalized_identity = _normalize(identity)
            if not normalized_identity:
                continue
            if normalized_query == normalized_identity:
                scores.append(300)
            elif normalized_identity in normalized_query:
                scores.append(240 if identity in card.course_numbers else 200)
            elif len(normalized_query) >= 5 and normalized_query in normalized_identity:
                scores.append(130)
        return max(scores, default=0)

    @staticmethod
    def _direction_score(card: CourseCard, directions: tuple[str, ...], query: str) -> int:
        haystack = " ".join([card.title, *card.aliases, *card.categories]).casefold()
        score = 0
        for direction in directions:
            markers = _DIRECTION_MARKERS.get(direction, ())
            if any(marker.casefold() in haystack for marker in markers):
                score += 90
        query_lowered = query.casefold()
        for markers in _DIRECTION_MARKERS.values():
            requested = [marker for marker in markers if marker.casefold() in query_lowered]
            if requested and any(marker.casefold() in haystack for marker in requested):
                score += 70
        return score


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogDataError(f"{label} must be non-empty text")
    return value.strip()


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, (str, int, float)) for item in value):
        raise CatalogDataError(f"{label} must be a scalar list")
    return [str(item).strip() for item in value if str(item).strip()]


def _validated_url(value: Any, label: str, *, required_host: str | None = None) -> str:
    text = _required_text(value, label)
    parsed = urlparse(text)
    if parsed.scheme != "https" or not parsed.netloc:
        raise CatalogDataError(f"{label} must be an HTTPS URL")
    if required_host and parsed.hostname != required_host:
        raise CatalogDataError(f"{label} must use {required_host}")
    return text


def _normalize(value: str) -> str:
    return re.sub(r"[^\w]+", "", value.casefold(), flags=re.UNICODE)


def _manifest_matches_target(manifest: dict[str, Any], target: dict[str, Any]) -> bool:
    target_numbers = {_normalize(str(value)) for value in target.get("course_numbers", [])}
    manifest_numbers = {
        _normalize(str(manifest.get("primary_course_number") or "")),
        *(
            _normalize(str(value))
            for value in (manifest.get("cross_listed_course_numbers") or [])
        ),
    }
    if target_numbers and target_numbers.intersection(manifest_numbers):
        return True
    target_id = _normalize(str(target.get("canonical_course_id") or ""))
    manifest_id = _normalize(str(manifest.get("course_id") or ""))
    return bool(
        target_id
        and manifest_id
        and (target_id in manifest_id or manifest_id in target_id)
    )
