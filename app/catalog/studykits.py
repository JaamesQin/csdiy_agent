"""Validated read access to StudyKits that are safe for online use.

The online runtime can read explicitly approved documents from the private
SQLite archive.  The two tracked, human-approved golden StudyKits remain a
fallback so an empty or unavailable archive does not remove existing online
capabilities.  ``validated_draft`` archive records are never online-ready.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Protocol

from app.agent.contracts import CourseContext
from app.agent.numbers import parse_positive_int
from app.catalog.contracts import ReadyStudyKitSummary
from app.retrieval.schema_validation import validate_yaml


_SUPPORTED_ARCHIVE_SCHEMAS = {
    "portable-v0.1-reviewed-legacy",
    "portable-v0.2.1",
    "portable-v0.2.2",
}
_ARCHIVE_TABLE_COLUMNS = {
    "studykit_builds": {
        "build_id",
        "course_id",
        "course_version",
        "build_status",
        "review_status",
        "schema_id",
        "unit_count",
    },
    "studykit_documents": {
        "course_id",
        "course_version",
        "unit_id",
        "build_id",
        "title",
        "document_status",
        "review_status",
        "schema_id",
        "document_sha256",
        "document_json",
    },
    "studykit_artifacts": {
        "build_id",
        "relative_path",
        "sha256",
        "content",
    },
}
_UNIT_REFERENCE = re.compile(
    r"(?:lecture\s*[- ]?(0?[0-9]{1,3})|第\s*([零〇一二两三四五六七八九十百千0-9]{1,8})\s*讲)",
    re.IGNORECASE,
)


class StudyKitArchiveError(RuntimeError):
    """Raised when the private StudyKit archive cannot be trusted."""


class StudyKitStore(Protocol):
    """Read-only access to StudyKits that are safe for online use."""

    def get_ready(
        self, course_id: str, course_version: str, unit_id: str
    ) -> dict[str, Any] | None:
        """Return one reviewed StudyKit, or ``None`` when it is unavailable."""

    def list_ready(
        self,
        *,
        course_id: str | None = None,
        course_version: str | None = None,
    ) -> list[ReadyStudyKitSummary]:
        """List public summaries for reviewed StudyKits matching the filters."""

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


class _DocumentStudyKitStore:
    """Shared identity and summary behavior for immutable document stores."""

    def _load(self) -> dict[tuple[str, str, str], dict[str, Any]]:
        raise NotImplementedError

    def get_ready(
        self, course_id: str, course_version: str, unit_id: str
    ) -> dict[str, Any] | None:
        document = self._load().get((course_id, course_version, self._normalize_unit(unit_id)))
        return copy.deepcopy(document) if document is not None else None

    def list_ready(
        self,
        *,
        course_id: str | None = None,
        course_version: str | None = None,
    ) -> list[ReadyStudyKitSummary]:
        summaries: list[ReadyStudyKitSummary] = []
        for (known_course, known_version, known_unit), document in self._load().items():
            if course_id is not None and course_id != known_course:
                continue
            if course_version is not None and course_version != known_version:
                continue
            source = next(
                (
                    item
                    for item in document.get("scope", {}).get("included_sources", [])
                    if isinstance(item, dict)
                ),
                None,
            )
            estimated = document.get("estimated_study_time_minutes")
            if not isinstance(estimated, int) or estimated <= 0:
                durations = [
                    item.get("duration_minutes")
                    for item in document.get("learning_sequence", [])
                    if isinstance(item, dict)
                ]
                estimated = (
                    sum(value for value in durations if isinstance(value, int) and value > 0)
                    or None
                )
            summaries.append(
                ReadyStudyKitSummary(
                    course_id=known_course,
                    course_version=known_version,
                    unit_id=known_unit,
                    title=str(document["title"]),
                    estimated_study_time_minutes=estimated,
                    official_url=(
                        str(source["official_url"])
                        if source and source.get("official_url")
                        else None
                    ),
                )
            )
        return sorted(
            summaries,
            key=lambda item: (item.course_id, item.course_version, item.unit_id),
        )

    def resolve_context(
        self,
        *,
        course_id: str | None = None,
        course_version: str | None = None,
        unit_id: str | None = None,
    ) -> CourseContext | None:
        normalized_unit = self._normalize_unit(unit_id) if unit_id is not None else None
        matches = [
            identity
            for identity in self._load()
            if (course_id is None or identity[0] == course_id)
            and (course_version is None or identity[1] == course_version)
            and (normalized_unit is None or identity[2] == normalized_unit)
        ]
        if not matches:
            return None
        courses = {(course, version) for course, version, _ in matches}
        if len(courses) != 1:
            return None
        known_course, known_version = next(iter(courses))
        matched_units = {unit for _, _, unit in matches}
        resolved_unit = next(iter(matched_units)) if len(matched_units) == 1 else None
        document = (
            self._load().get((known_course, known_version, resolved_unit))
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
        documents = self._load()
        course_pairs = sorted({(course, version) for course, version, _ in documents})
        selected: tuple[str, str] | None = None
        selected_unit: str | None = None

        for text in texts:
            matches = self._matching_courses(text, course_pairs)
            if len(matches) == 1:
                selected = next(iter(matches))
            unit_matches = list(_UNIT_REFERENCE.finditer(text))
            if unit_matches:
                match = unit_matches[-1]
                number = parse_positive_int(match.group(1) or match.group(2))
                if number is not None:
                    selected_unit = f"lecture-{number:02d}"

        if selected is None and selected_unit is None:
            return None
        return self.resolve_context(
            course_id=selected[0] if selected else None,
            course_version=selected[1] if selected else None,
            unit_id=selected_unit,
        )

    @classmethod
    def _matching_courses(
        cls,
        text: str,
        course_pairs: list[tuple[str, str]],
    ) -> set[tuple[str, str]]:
        normalized_text = _normalize_identity(text)
        exact: set[tuple[str, str]] = set()
        base: set[tuple[str, str]] = set()
        for course_id, version in course_pairs:
            full_alias = _normalize_identity(course_id)
            if full_alias and full_alias in normalized_text:
                exact.add((course_id, version))
                continue
            aliases = cls._course_aliases(course_id, version)
            words = {
                _normalize_identity(word)
                for word in re.split(r"[^\w]+", cls._course_base(course_id, version))
                if len(_normalize_identity(word)) >= 4
            }
            token_match = sum(word in normalized_text for word in words) >= 2
            if any(alias in normalized_text for alias in aliases) or token_match:
                base.add((course_id, version))
        if exact:
            return exact
        if len(base) > 1:
            version_matches = {
                pair for pair in base if _normalize_identity(pair[1]) in normalized_text
            }
            if version_matches:
                return version_matches
        return base

    @staticmethod
    def _course_aliases(course_id: str, course_version: str) -> set[str]:
        base = _DocumentStudyKitStore._course_base(course_id, course_version)
        aliases = {
            _normalize_identity(base),
            _normalize_identity(course_id.replace("-", " ")),
            _normalize_identity(base.replace("-", " ")),
        }
        return {alias for alias in aliases if len(alias) >= 5}

    @staticmethod
    def _course_base(course_id: str, course_version: str) -> str:
        base = course_id
        suffix = f"-{course_version}"
        if base.casefold().endswith(suffix.casefold()):
            base = base[: -len(suffix)]
        return base

    @staticmethod
    def _normalize_unit(value: str) -> str:
        lowered = value.strip().lower()
        match = re.fullmatch(
            r"(?:lecture\s*[- ]?0?([0-9]{1,3})|第\s*([零〇一二两三四五六七八九十百千0-9]{1,8})\s*讲)",
            lowered,
        )
        if match:
            number = parse_positive_int(match.group(1) or match.group(2))
            if number is not None:
                return f"lecture-{number:02d}"
        return lowered


class ReviewedFileStudyKitStore(_DocumentStudyKitStore):
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
            identity = _document_identity(document)
            documents[identity] = document
        self._documents = documents
        return documents


class ArchivedStudyKitStore(_DocumentStudyKitStore):
    """Read explicitly approved StudyKits from the immutable SQLite archive."""

    def __init__(self, archive_path: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[2]
        self._archive_path = archive_path or root / "data" / "archive" / "studykits.sqlite3"
        self._documents: dict[tuple[str, str, str], dict[str, Any]] | None = None

    def _load(self) -> dict[tuple[str, str, str], dict[str, Any]]:
        if self._documents is not None:
            return self._documents
        try:
            documents = self._read_archive()
        except StudyKitArchiveError:
            raise
        except (OSError, sqlite3.Error, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise StudyKitArchiveError("StudyKit archive is unreadable or invalid") from exc
        self._documents = documents
        return documents

    def _read_archive(self) -> dict[tuple[str, str, str], dict[str, Any]]:
        if not self._archive_path.is_file():
            raise StudyKitArchiveError("StudyKit archive is missing")
        uri = f"{self._archive_path.resolve().as_uri()}?mode=ro&immutable=1"
        with sqlite3.connect(uri, uri=True) as connection:
            connection.row_factory = sqlite3.Row
            if int(connection.execute("PRAGMA user_version").fetchone()[0]) != 1:
                raise StudyKitArchiveError("unsupported StudyKit archive version")
            quick_check = connection.execute("PRAGMA quick_check").fetchone()
            if quick_check is None or quick_check[0] != "ok":
                raise StudyKitArchiveError("StudyKit archive failed quick_check")
            self._validate_tables(connection)
            rows = connection.execute(
                """
                SELECT
                    d.course_id,
                    d.course_version,
                    d.unit_id,
                    d.title,
                    d.schema_id AS document_schema_id,
                    d.document_sha256,
                    d.document_json,
                    b.schema_id AS build_schema_id
                FROM studykit_documents AS d
                JOIN studykit_builds AS b ON b.build_id = d.build_id
                WHERE d.review_status = 'approved'
                  AND d.document_status IN ('draft', 'reviewed', 'published')
                  AND b.review_status = 'approved'
                  AND b.build_status = 'succeeded'
                ORDER BY d.course_id, d.course_version, d.unit_id
                """
            ).fetchall()

        documents: dict[tuple[str, str, str], dict[str, Any]] = {}
        for row in rows:
            schema_id = str(row["document_schema_id"])
            if schema_id != str(row["build_schema_id"]):
                raise StudyKitArchiveError("archive build/document schema mismatch")
            if schema_id not in _SUPPORTED_ARCHIVE_SCHEMAS:
                raise StudyKitArchiveError(f"unsupported approved StudyKit schema: {schema_id}")
            raw_json = str(row["document_json"])
            digest = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
            if digest != row["document_sha256"]:
                raise StudyKitArchiveError("approved StudyKit document hash mismatch")
            document = json.loads(raw_json)
            if not isinstance(document, dict):
                raise StudyKitArchiveError("approved StudyKit document is not an object")
            identity = (
                str(row["course_id"]),
                str(row["course_version"]),
                str(row["unit_id"]),
            )
            if _document_identity(document) != identity:
                raise StudyKitArchiveError("approved StudyKit identity mismatch")
            if str(document.get("title")) != str(row["title"]):
                raise StudyKitArchiveError("approved StudyKit title mismatch")
            _validate_runtime_document(document)
            documents[identity] = document
        return documents

    @staticmethod
    def _validate_tables(connection: sqlite3.Connection) -> None:
        for table, required in _ARCHIVE_TABLE_COLUMNS.items():
            rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
            columns = {str(row[1]) for row in rows}
            if not required.issubset(columns):
                raise StudyKitArchiveError(f"StudyKit archive table is incompatible: {table}")


class CompositeStudyKitStore(_DocumentStudyKitStore):
    """Prefer approved archive documents while retaining reviewed golden data."""

    def __init__(
        self,
        primary: StudyKitStore,
        fallback: StudyKitStore,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._documents: dict[tuple[str, str, str], dict[str, Any]] | None = None

    def _load(self) -> dict[tuple[str, str, str], dict[str, Any]]:
        if self._documents is not None:
            return self._documents
        documents = _collect_documents(self._fallback)
        try:
            documents.update(_collect_documents(self._primary))
        except StudyKitArchiveError:
            # An unavailable or invalid private archive must not remove the
            # already reviewed golden online surface.
            pass
        self._documents = documents
        return documents


def build_default_studykit_store() -> CompositeStudyKitStore:
    """Build the database-first, reviewed-golden-fallback runtime store."""

    return CompositeStudyKitStore(
        ArchivedStudyKitStore(),
        ReviewedFileStudyKitStore(),
    )


def _collect_documents(store: StudyKitStore) -> dict[tuple[str, str, str], dict[str, Any]]:
    documents: dict[tuple[str, str, str], dict[str, Any]] = {}
    for summary in store.list_ready():
        document = store.get_ready(summary.course_id, summary.course_version, summary.unit_id)
        if document is not None:
            documents[(summary.course_id, summary.course_version, summary.unit_id)] = document
    return documents


def _document_identity(document: dict[str, Any]) -> tuple[str, str, str]:
    values = (document.get("course_id"), document.get("course_version"), document.get("unit_id"))
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise StudyKitArchiveError("StudyKit document identity is incomplete")
    return tuple(str(value) for value in values)  # type: ignore[return-value]


def _validate_runtime_document(document: dict[str, Any]) -> None:
    if not isinstance(document.get("title"), str) or not document["title"].strip():
        raise StudyKitArchiveError("approved StudyKit has no title")
    for field in ("learning_objectives", "core_concepts", "practice"):
        if not isinstance(document.get(field), list) or not document[field]:
            raise StudyKitArchiveError(f"approved StudyKit has no usable {field}")

    practices = document["practice"]
    for item in practices:
        if not isinstance(item, dict):
            raise StudyKitArchiveError("approved StudyKit practice entry is not an object")
        for key in ("id", "level", "question", "hint", "deliverable"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise StudyKitArchiveError(f"approved StudyKit practice entry missing {key}")

    scope = document.get("scope")
    if not isinstance(scope, dict) or not isinstance(scope.get("included_sources"), list):
        raise StudyKitArchiveError("approved StudyKit has no usable source scope")


def _normalize_identity(value: str) -> str:
    return re.sub(r"[^\w]+", "", value.casefold(), flags=re.UNICODE)
