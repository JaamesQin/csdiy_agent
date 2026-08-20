"""SQLite archive for validated offline StudyKit builds.

This store is deliberately separate from the account/profile database.  It
preserves portable authoring artifacts and their review state without making a
validated draft visible to the online learner runtime.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ARCHIVE_SCHEMA_VERSION = 1
READY_REVIEW_STATUSES = frozenset({"approved"})


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class ArchivedBuild:
    build_id: str
    course_id: str
    course_version: str
    build_status: str
    review_status: str
    unit_count: int
    content_sha256: str


class StudyKitArchive:
    """Own and query an auditable, latest-build-only StudyKit SQLite archive."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version not in {0, ARCHIVE_SCHEMA_VERSION}:
                raise RuntimeError(f"unsupported StudyKit archive version: {version}")
            if version == ARCHIVE_SCHEMA_VERSION:
                return
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS studykit_builds (
                    build_id TEXT PRIMARY KEY,
                    course_id TEXT NOT NULL,
                    course_version TEXT NOT NULL,
                    build_status TEXT NOT NULL,
                    review_status TEXT NOT NULL CHECK (
                        review_status IN ('validated_draft', 'approved')
                    ),
                    schema_id TEXT NOT NULL,
                    quality_mode TEXT,
                    delivery_policy TEXT,
                    unit_count INTEGER NOT NULL CHECK (unit_count > 0),
                    content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
                    imported_at TEXT NOT NULL,
                    source_label TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    UNIQUE (course_id, course_version)
                );

                CREATE TABLE IF NOT EXISTS studykit_documents (
                    course_id TEXT NOT NULL,
                    course_version TEXT NOT NULL,
                    unit_id TEXT NOT NULL,
                    build_id TEXT NOT NULL REFERENCES studykit_builds(build_id)
                        ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    document_status TEXT NOT NULL,
                    review_status TEXT NOT NULL,
                    schema_id TEXT NOT NULL,
                    document_sha256 TEXT NOT NULL CHECK (length(document_sha256) = 64),
                    document_json TEXT NOT NULL,
                    learner_markdown TEXT,
                    PRIMARY KEY (course_id, course_version, unit_id)
                );

                CREATE INDEX IF NOT EXISTS idx_studykit_documents_build
                    ON studykit_documents(build_id);

                CREATE TABLE IF NOT EXISTS studykit_artifacts (
                    build_id TEXT NOT NULL REFERENCES studykit_builds(build_id)
                        ON DELETE CASCADE,
                    relative_path TEXT NOT NULL,
                    unit_id TEXT,
                    media_type TEXT NOT NULL,
                    byte_size INTEGER NOT NULL CHECK (byte_size >= 0),
                    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
                    content BLOB NOT NULL,
                    PRIMARY KEY (build_id, relative_path)
                );
                """
            )
            connection.execute(f"PRAGMA user_version = {ARCHIVE_SCHEMA_VERSION}")

    def list_builds(self) -> list[ArchivedBuild]:
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT build_id, course_id, course_version, build_status,
                       review_status, unit_count, content_sha256
                FROM studykit_builds
                ORDER BY course_id, course_version
                """
            ).fetchall()
        return [ArchivedBuild(**dict(row)) for row in rows]

    def get_document(
        self,
        course_id: str,
        course_version: str,
        unit_id: str,
        *,
        ready_only: bool = True,
    ) -> dict[str, Any] | None:
        self.initialize()
        query = """
            SELECT document_json, review_status
            FROM studykit_documents
            WHERE course_id = ? AND course_version = ? AND unit_id = ?
        """
        with self.connect() as connection:
            row = connection.execute(
                query, (course_id, course_version, unit_id)
            ).fetchone()
        if row is None:
            return None
        if ready_only and row["review_status"] not in READY_REVIEW_STATUSES:
            return None
        value = json.loads(row["document_json"])
        if not isinstance(value, dict):
            raise RuntimeError("archived StudyKit is not a JSON object")
        return value

    def verify_integrity(self) -> list[str]:
        """Re-hash every document/artifact and reconcile build unit counts."""

        self.initialize()
        issues: list[str] = []
        with self.connect() as connection:
            for row in connection.execute(
                "SELECT build_id, unit_count, content_sha256 FROM studykit_builds"
            ):
                docs = connection.execute(
                    """
                    SELECT unit_id, document_sha256, document_json
                    FROM studykit_documents WHERE build_id = ? ORDER BY unit_id
                    """,
                    (row["build_id"],),
                ).fetchall()
                if len(docs) != row["unit_count"]:
                    issues.append(
                        f"{row['build_id']}: unit_count {row['unit_count']} != {len(docs)}"
                    )
                digests: list[str] = []
                for doc in docs:
                    content = doc["document_json"].encode("utf-8")
                    digest = sha256_bytes(content)
                    if digest != doc["document_sha256"]:
                        issues.append(
                            f"{row['build_id']}/{doc['unit_id']}: document hash mismatch"
                        )
                    digests.append(f"{doc['unit_id']}:{digest}")
                aggregate = sha256_bytes("\n".join(digests).encode("utf-8"))
                if aggregate != row["content_sha256"]:
                    issues.append(f"{row['build_id']}: aggregate hash mismatch")

            for artifact in connection.execute(
                "SELECT build_id, relative_path, sha256, byte_size, content FROM studykit_artifacts"
            ):
                content = bytes(artifact["content"])
                if len(content) != artifact["byte_size"]:
                    issues.append(
                        f"{artifact['build_id']}/{artifact['relative_path']}: size mismatch"
                    )
                if sha256_bytes(content) != artifact["sha256"]:
                    issues.append(
                        f"{artifact['build_id']}/{artifact['relative_path']}: hash mismatch"
                    )
        return issues
