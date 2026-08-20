"""Persistent, minimized conversation continuity keyed by opaque gateway sessions."""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from pydantic import ValidationError

from app.agent.context_token import ConversationState
from app.storage.database import SQLiteDatabase


@dataclass(frozen=True, slots=True)
class LoadedConversationState:
    state: ConversationState
    revision: int


class SessionStateStore(Protocol):
    def load(self, namespace: str, session_id: str) -> LoadedConversationState | None: ...

    def save(
        self,
        namespace: str,
        session_id: str,
        state: ConversationState,
        *,
        expected_revision: int | None,
    ) -> bool: ...


class SQLiteSessionStateStore:
    """CAS-protected SQLite state without raw session identifiers."""

    def __init__(
        self,
        database: SQLiteDatabase,
        *,
        key_secret: bytes,
        ttl_days: int = 30,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if len(key_secret) < 32:
            raise ValueError("session state key secret must be at least 32 bytes")
        if ttl_days <= 0:
            raise ValueError("session state TTL must be positive")
        self.database = database
        self._key_secret = key_secret
        self._ttl = timedelta(days=ttl_days)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.RLock()

    def load(self, namespace: str, session_id: str) -> LoadedConversationState | None:
        key = self._key(namespace, session_id)
        now = self._now()
        with self._lock, self.database.connect() as connection:
            connection.execute(
                "DELETE FROM conversation_states WHERE expires_at <= ?",
                (now.isoformat(),),
            )
            row = connection.execute(
                """
                SELECT state_json, revision
                FROM conversation_states
                WHERE session_key_hash = ? AND expires_at > ?
                """,
                (key, now.isoformat()),
            ).fetchone()
            if row is None:
                return None
            try:
                state = ConversationState.model_validate_json(row["state_json"])
            except (ValidationError, ValueError, json.JSONDecodeError):
                connection.execute(
                    "DELETE FROM conversation_states WHERE session_key_hash = ?",
                    (key,),
                )
                return None
        return LoadedConversationState(state=state, revision=int(row["revision"]))

    def save(
        self,
        namespace: str,
        session_id: str,
        state: ConversationState,
        *,
        expected_revision: int | None,
    ) -> bool:
        key = self._key(namespace, session_id)
        serialized = state.model_dump_json()
        if len(serialized.encode("utf-8")) > 65_536:
            raise ValueError("conversation state exceeds storage limit")
        now = self._now()
        expires_at = now + self._ttl
        with self._lock, self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM conversation_states WHERE expires_at <= ?",
                (now.isoformat(),),
            )
            if expected_revision is None:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO conversation_states (
                        session_key_hash, state_json, revision,
                        created_at, updated_at, expires_at
                    ) VALUES (?, ?, 1, ?, ?, ?)
                    """,
                    (
                        key,
                        serialized,
                        now.isoformat(),
                        now.isoformat(),
                        expires_at.isoformat(),
                    ),
                )
            else:
                cursor = connection.execute(
                    """
                    UPDATE conversation_states
                    SET state_json = ?, revision = revision + 1,
                        updated_at = ?, expires_at = ?
                    WHERE session_key_hash = ? AND revision = ?
                    """,
                    (
                        serialized,
                        now.isoformat(),
                        expires_at.isoformat(),
                        key,
                        expected_revision,
                    ),
                )
            return cursor.rowcount == 1

    def _key(self, namespace: str, session_id: str) -> str:
        if not namespace.strip() or not session_id.strip():
            raise ValueError("conversation namespace and session ID must be non-empty")
        material = f"{namespace}\0{session_id}".encode("utf-8")
        return hmac.new(self._key_secret, material, hashlib.sha256).hexdigest()

    def _now(self) -> datetime:
        value = self._clock()
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
