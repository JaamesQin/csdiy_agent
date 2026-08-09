"""SQLite persistence for evidence-aware learner profile facts."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.profile.contracts import FactStatus, LearnerProfile, ProfileFact, ProfileFieldName

SCHEMA_VERSION = 1
SCALAR_FIELDS: set[str] = {
    "weekly_minutes",
    "preferred_explanation_style",
    "active_course",
    "active_unit",
}


class SQLiteProfileRepository:
    """Small transactional fact store; connections are never shared across threads."""

    def __init__(self, path: Path | str | None = None) -> None:
        root = Path(__file__).resolve().parents[2]
        configured = path or os.getenv("COURSEPILOT_DB_PATH")
        self.path = Path(configured) if configured else root / "storage" / "coursepilot.sqlite3"
        self._initialized = False
        self._lock = threading.RLock()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return
            with self._connect() as connection:
                connection.execute("PRAGMA journal_mode = WAL")
                current = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if current not in {0, SCHEMA_VERSION}:
                    raise RuntimeError(f"unsupported profile database version: {current}")
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS profile_facts (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        field_name TEXT NOT NULL,
                        value_json TEXT,
                        status TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        evidence_excerpt TEXT,
                        course_id TEXT,
                        course_version TEXT,
                        unit_id TEXT,
                        created_at TEXT NOT NULL,
                        expires_at TEXT,
                        superseded_at TEXT
                    );
                    CREATE INDEX IF NOT EXISTS idx_profile_facts_user_active
                    ON profile_facts(user_id, superseded_at, expires_at);
                    """
                )
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self._initialized = True

    def add_fact(
        self,
        *,
        user_id: str,
        field_name: ProfileFieldName,
        value: Any,
        status: FactStatus,
        confidence: float,
        evidence_excerpt: str | None,
        course_id: str | None = None,
        course_version: str | None = None,
        unit_id: str | None = None,
        expires_at: datetime | None = None,
        replace: bool | None = None,
    ) -> ProfileFact:
        self.initialize()
        now = datetime.now(UTC)
        fact = ProfileFact(
            id=uuid.uuid4().hex,
            user_id=user_id,
            field_name=field_name,
            value=value,
            status=status,
            confidence=confidence,
            evidence_excerpt=evidence_excerpt,
            course_id=course_id,
            course_version=course_version,
            unit_id=unit_id,
            created_at=now,
            expires_at=expires_at,
        )
        should_replace = field_name in SCALAR_FIELDS if replace is None else replace
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if should_replace:
                connection.execute(
                    """
                    UPDATE profile_facts SET superseded_at = ?
                    WHERE user_id = ? AND field_name = ? AND superseded_at IS NULL
                    """,
                    (now.isoformat(), user_id, field_name),
                )
            else:
                existing = connection.execute(
                    """
                    SELECT id FROM profile_facts
                    WHERE user_id = ? AND field_name = ? AND value_json = ?
                      AND status = ? AND superseded_at IS NULL
                      AND (expires_at IS NULL OR expires_at > ?)
                    LIMIT 1
                    """,
                    (
                        user_id,
                        field_name,
                        json.dumps(value, ensure_ascii=False, sort_keys=True),
                        status.value,
                        now.isoformat(),
                    ),
                ).fetchone()
                if existing is not None:
                    connection.rollback()
                    profile = self.get_profile(user_id)
                    return next(item for item in profile.facts if item.id == existing["id"])
            connection.execute(
                """
                INSERT INTO profile_facts (
                    id, user_id, field_name, value_json, status, confidence,
                    evidence_excerpt, course_id, course_version, unit_id,
                    created_at, expires_at, superseded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    fact.id,
                    user_id,
                    field_name,
                    json.dumps(value, ensure_ascii=False, sort_keys=True),
                    status.value,
                    confidence,
                    evidence_excerpt,
                    course_id,
                    course_version,
                    unit_id,
                    now.isoformat(),
                    expires_at.isoformat() if expires_at else None,
                ),
            )
        return fact

    def get_profile(self, user_id: str) -> LearnerProfile:
        self.initialize()
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM profile_facts
                WHERE user_id = ? AND superseded_at IS NULL
                  AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY created_at, id
                """,
                (user_id, now),
            ).fetchall()
        return LearnerProfile(
            user_id=user_id,
            persisted=True,
            facts=[self._row_to_fact(row) for row in rows],
        )

    def confirm_inferred(self, user_id: str) -> int:
        self.initialize()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE profile_facts
                SET status = ?, confidence = 1.0, expires_at = NULL
                WHERE user_id = ? AND status = ? AND superseded_at IS NULL
                """,
                (FactStatus.CONFIRMED.value, user_id, FactStatus.INFERRED.value),
            )
        return int(cursor.rowcount)

    def delete_field(self, user_id: str, field_name: ProfileFieldName) -> int:
        self.initialize()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "DELETE FROM profile_facts WHERE user_id = ? AND field_name = ?",
                (user_id, field_name),
            )
        return int(cursor.rowcount)

    def delete_all(self, user_id: str) -> int:
        self.initialize()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "DELETE FROM profile_facts WHERE user_id = ?", (user_id,)
            )
        return int(cursor.rowcount)

    @staticmethod
    def _row_to_fact(row: sqlite3.Row) -> ProfileFact:
        return ProfileFact(
            id=row["id"],
            user_id=row["user_id"],
            field_name=row["field_name"],
            value=json.loads(row["value_json"]) if row["value_json"] is not None else None,
            status=FactStatus(row["status"]),
            confidence=float(row["confidence"]),
            evidence_excerpt=row["evidence_excerpt"],
            course_id=row["course_id"],
            course_version=row["course_version"],
            unit_id=row["unit_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            expires_at=(datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None),
        )
