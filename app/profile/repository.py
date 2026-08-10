"""SQLite learner profile facts keyed by a trusted subject identifier."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from app.storage.database import SQLiteDatabase

SCALAR_FIELDS = {"learning_direction", "weekly_minutes", "background"}


class SQLiteProfileRepository:
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database
        self._lock = threading.RLock()

    def set_fact(
        self,
        *,
        user_id: str,
        field_name: str,
        value: Any,
        evidence_excerpt: str,
    ) -> None:
        now = datetime.now(UTC)
        with self._lock, self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if field_name in SCALAR_FIELDS:
                connection.execute(
                    """
                    UPDATE profile_facts SET superseded_at = ?
                    WHERE user_id = ? AND field_name = ? AND superseded_at IS NULL
                    """,
                    (now.isoformat(), user_id, field_name),
                )
            connection.execute(
                """
                INSERT INTO profile_facts (
                    id, user_id, field_name, value_json, status, confidence,
                    evidence_excerpt, course_id, course_version, unit_id,
                    created_at, expires_at, superseded_at
                ) VALUES (?, ?, ?, ?, 'confirmed', 1.0, ?, NULL, NULL, NULL, ?, NULL, NULL)
                """,
                (
                    uuid.uuid4().hex,
                    user_id,
                    field_name,
                    json.dumps(value, ensure_ascii=False, sort_keys=True),
                    evidence_excerpt[:160],
                    now.isoformat(),
                ),
            )

    def get_profile(self, user_id: str) -> dict[str, list[Any]]:
        now = datetime.now(UTC).isoformat()
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT field_name, value_json FROM profile_facts
                WHERE user_id = ? AND superseded_at IS NULL
                  AND (expires_at IS NULL OR expires_at > ?)
                  AND status = 'confirmed'
                ORDER BY created_at, id
                """,
                (user_id, now),
            ).fetchall()
        profile: dict[str, list[Any]] = {}
        for row in rows:
            profile.setdefault(row["field_name"], []).append(
                json.loads(row["value_json"])
            )
        return profile

    def delete_all(self, user_id: str) -> int:
        with self._lock, self.database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM profile_facts WHERE user_id = ?",
                (user_id,),
            )
        return int(cursor.rowcount)
