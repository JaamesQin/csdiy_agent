"""Shared-SQLite persistence for evidence-aware learner profile facts."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.profile.contracts import FactStatus, LearnerProfile, ProfileFact, ProfileFieldName
from app.storage.database import SQLiteDatabase

SCALAR_FIELDS: set[str] = {
    "weekly_minutes",
    "preferred_explanation_style",
    "active_course",
    "active_unit",
}


class SQLiteProfileRepository:
    """Transactional fact store using the same schema owner as account sessions."""

    def __init__(
        self, database: SQLiteDatabase | Path | str | None = None
    ) -> None:
        self.database = (
            database if isinstance(database, SQLiteDatabase) else SQLiteDatabase(database)
        )
        self._lock = threading.RLock()

    def initialize(self) -> None:
        self.database.initialize()

    def _connect(self) -> sqlite3.Connection:
        return self.database.connect()

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
        now = datetime.now(UTC)
        fact = ProfileFact(
            id=uuid.uuid4().hex,
            user_id=user_id,
            field_name=field_name,
            value=value,
            status=status,
            confidence=confidence,
            evidence_excerpt=(evidence_excerpt[:200] if evidence_excerpt else None),
            course_id=course_id,
            course_version=course_version,
            unit_id=unit_id,
            created_at=now,
            expires_at=expires_at,
        )
        should_replace = field_name in SCALAR_FIELDS if replace is None else replace
        serialized_value = json.dumps(value, ensure_ascii=False, sort_keys=True)
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
                        serialized_value,
                        status.value,
                        now.isoformat(),
                    ),
                ).fetchone()
                if existing is not None:
                    existing_id = str(existing["id"])
                    connection.rollback()
                    return next(
                        item
                        for item in self.get_profile(user_id).facts
                        if item.id == existing_id
                    )
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
                    serialized_value,
                    status.value,
                    confidence,
                    fact.evidence_excerpt,
                    course_id,
                    course_version,
                    unit_id,
                    now.isoformat(),
                    expires_at.isoformat() if expires_at else None,
                ),
            )
        return fact

    def get_profile(self, user_id: str) -> LearnerProfile:
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
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "DELETE FROM profile_facts WHERE user_id = ? AND field_name = ?",
                (user_id, field_name),
            )
        return int(cursor.rowcount)

    def delete_all(self, user_id: str) -> int:
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
            expires_at=(
                datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None
            ),
        )
