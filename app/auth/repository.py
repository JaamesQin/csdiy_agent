"""SQLite repositories for accounts and opaque sessions."""

from __future__ import annotations

import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.storage.database import SQLiteDatabase


class DuplicateUsernameError(ValueError):
    pass


@dataclass(frozen=True)
class UserRecord:
    id: str
    username: str
    username_normalized: str
    password_hash: str
    created_at: datetime
    updated_at: datetime
    disabled_at: datetime | None


@dataclass(frozen=True)
class SessionRecord:
    token_hash: str
    user: UserRecord
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class SQLiteAuthRepository:
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database
        self._lock = threading.RLock()

    def create_user(
        self, *, username: str, username_normalized: str, password_hash: str
    ) -> UserRecord:
        now = datetime.now(UTC)
        record = UserRecord(
            id=uuid.uuid4().hex,
            username=username,
            username_normalized=username_normalized,
            password_hash=password_hash,
            created_at=now,
            updated_at=now,
            disabled_at=None,
        )
        try:
            with self._lock, self.database.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO users (
                        id, username, username_normalized, password_hash,
                        created_at, updated_at, disabled_at
                    ) VALUES (?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        record.id,
                        record.username,
                        record.username_normalized,
                        record.password_hash,
                        record.created_at.isoformat(),
                        record.updated_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateUsernameError("Username is unavailable") from exc
        return record

    def get_user_by_normalized(self, username_normalized: str) -> UserRecord | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username_normalized = ?",
                (username_normalized,),
            ).fetchone()
        return self._row_to_user(row) if row is not None else None

    def update_password_hash(self, user_id: str, password_hash: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self._lock, self.database.connect() as connection:
            connection.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (password_hash, now, user_id),
            )

    def create_session(
        self,
        *,
        user: UserRecord,
        token_hash: str,
        expires_at: datetime,
    ) -> SessionRecord:
        now = datetime.now(UTC)
        with self._lock, self.database.connect() as connection:
            connection.execute(
                "DELETE FROM auth_sessions WHERE expires_at <= ? OR revoked_at IS NOT NULL",
                (now.isoformat(),),
            )
            connection.execute(
                """
                INSERT INTO auth_sessions (
                    token_hash, user_id, created_at, expires_at, revoked_at
                ) VALUES (?, ?, ?, ?, NULL)
                """,
                (token_hash, user.id, now.isoformat(), expires_at.isoformat()),
            )
        return SessionRecord(
            token_hash=token_hash,
            user=user,
            created_at=now,
            expires_at=expires_at,
            revoked_at=None,
        )

    def get_active_session(self, token_hash: str) -> SessionRecord | None:
        now = datetime.now(UTC)
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    s.token_hash,
                    s.created_at AS session_created_at,
                    s.expires_at,
                    s.revoked_at,
                    u.*
                FROM auth_sessions AS s
                JOIN users AS u ON u.id = s.user_id
                WHERE s.token_hash = ?
                  AND s.revoked_at IS NULL
                  AND s.expires_at > ?
                  AND u.disabled_at IS NULL
                """,
                (token_hash, now.isoformat()),
            ).fetchone()
        if row is None:
            return None
        return SessionRecord(
            token_hash=row["token_hash"],
            user=self._row_to_user(row),
            created_at=datetime.fromisoformat(row["session_created_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]),
            revoked_at=(
                datetime.fromisoformat(row["revoked_at"])
                if row["revoked_at"]
                else None
            ),
        )

    def revoke_session(self, token_hash: str) -> None:
        with self._lock, self.database.connect() as connection:
            connection.execute(
                """
                UPDATE auth_sessions SET revoked_at = ?
                WHERE token_hash = ? AND revoked_at IS NULL
                """,
                (datetime.now(UTC).isoformat(), token_hash),
            )

    def delete_user(self, user_id: str) -> None:
        with self._lock, self.database.connect() as connection:
            connection.execute("DELETE FROM users WHERE id = ?", (user_id,))

    @staticmethod
    def _row_to_user(row: sqlite3.Row) -> UserRecord:
        return UserRecord(
            id=row["id"],
            username=row["username"],
            username_normalized=row["username_normalized"],
            password_hash=row["password_hash"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            disabled_at=(
                datetime.fromisoformat(row["disabled_at"])
                if row["disabled_at"]
                else None
            ),
        )
