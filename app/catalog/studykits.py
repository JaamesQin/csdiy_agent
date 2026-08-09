"""Validated read access to reviewed StudyKits.

The first online runtime deliberately reads only the two tracked, human-approved
golden StudyKits.  The protocol keeps the caller independent from this file-based
implementation so a database-backed catalog can replace it later.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Protocol

from app.agent.contracts import CourseContext
from app.retrieval.schema_validation import validate_yaml


class StudyKitStore(Protocol):
    """Read-only access to StudyKits that are safe for online use."""

    def get_ready(
        self, course_id: str, course_version: str, unit_id: str
    ) -> dict[str, Any] | None:
        """Return one reviewed StudyKit, or ``None`` when it is unavailable."""

    def resolve_context(
        self,
        *,
        course_id: str | None = None,
        course_version: str | None = None,
        unit_id: str | None = None,
    ) -> CourseContext | None:
        """Validate a possibly partial identity against known reviewed data."""

    def match_context(self, texts: list[str]) -> CourseContext | None:
        """Resolve the latest unambiguous course/unit reference in text."""


class ReviewedFileStudyKitStore:
    """Load schema-valid, human-approved golden StudyKits from the repository."""

    def __init__(
        self,
        golden_dir: Path | None = None,
        schema_path: Path | None = None,
    ) -> None:
        root = Path(__file__).resolve().parents[2]
        self._golden_dir = golden_dir or root / "data" / "golden"
        self._schema_path = schema_path or root / "schemas" / "studykit.schema.json"
        self._documents: dict[tuple[str, str, str], dict[str, Any]] | None = None

    def _load(self) -> dict[tuple[str, str, str], dict[str, Any]]:
        if self._documents is not None:
            return self._documents

        documents: dict[tuple[str, str, str], dict[str, Any]] = {}
        for path in sorted(self._golden_dir.glob("*-studykit.yaml")):
            document = validate_yaml(path, self._schema_path)
            if document.get("status") not in {"reviewed", "published"}:
                continue
            review = document.get("review")
            if not isinstance(review, dict) or review.get("human_review_status") != "approved":
                continue
            identity = (
                str(document["course_id"]),
                str(document["course_version"]),
                str(document["unit_id"]),
            )
            documents[identity] = document
        self._documents = documents
        return documents

    def get_ready(
        self, course_id: str, course_version: str, unit_id: str
    ) -> dict[str, Any] | None:
        return self._load().get((course_id, course_version, unit_id))

    def resolve_context(
        self,
        *,
        course_id: str | None = None,
        course_version: str | None = None,
        unit_id: str | None = None,
    ) -> CourseContext | None:
        matches: list[tuple[str, str, str]] = []
        for identity in self._load():
            known_course, known_version, known_unit = identity
            if course_id is not None and course_id != known_course:
                continue
            if course_version is not None and course_version != known_version:
                continue
            if unit_id is not None and self._normalize_unit(unit_id) != known_unit:
                continue
            matches.append(identity)

        if not matches:
            return None
        courses = {(course, version) for course, version, _ in matches}
        if len(courses) != 1:
            return None
        known_course, known_version = next(iter(courses))
        matched_units = {unit for _, _, unit in matches}
        resolved_unit = next(iter(matched_units)) if len(matched_units) == 1 else None
        document = (
            self.get_ready(known_course, known_version, resolved_unit)
            if resolved_unit is not None
            else None
        )
        return CourseContext(
            course_id=known_course,
            course_version=known_version,
            unit_id=resolved_unit,
            title=str(document["title"]) if document else None,
        )

    def match_context(self, texts: list[str]) -> CourseContext | None:
        course_id: str | None = None
        unit_id: str | None = None
        for text in texts:
            lowered = text.lower()
            if any(
                alias in lowered
                for alias in (
                    "mit 6.7960",
                    "mit6.7960",
                    "6.7960",
                    "mit-6.7960-fall-2024",
                )
            ):
                course_id = "mit-6.7960-fall-2024"
            unit_matches = list(
                re.finditer(
                    r"(?:lecture\s*[- ]?|第\s*)(0?[0-9]{1,2})(?:\s*讲)?",
                    lowered,
                )
            )
            if unit_matches:
                unit_id = f"lecture-{int(unit_matches[-1].group(1)):02d}"

        if course_id is None and unit_id is None:
            return None
        return self.resolve_context(course_id=course_id, unit_id=unit_id)

    @staticmethod
    def _normalize_unit(value: str) -> str:
        lowered = value.strip().lower()
        match = re.fullmatch(r"(?:lecture\s*[- ]?|第\s*)0?([0-9]{1,2})(?:\s*讲)?", lowered)
        if match:
            return f"lecture-{int(match.group(1)):02d}"
        return lowered
