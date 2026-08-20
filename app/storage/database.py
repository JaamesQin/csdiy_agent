"""Shared SQLite database and forward-only schema migration."""

from __future__ import annotations

import os
import sqlite3
import threading
from functools import lru_cache
from pathlib import Path

SCHEMA_VERSION = 3


class SQLiteDatabase:
    """Owns the SQLite path and serializes schema initialization."""

    def __init__(self, path: Path | str | None = None) -> None:
        root = Path(__file__).resolve().parents[2]
        configured = path or os.getenv("COURSEPILOT_DB_PATH")
        self.path = Path(configured) if configured else root / "storage" / "coursepilot.sqlite3"
        self._restrict_parent = configured is None
        self._initialized = False
        self._lock = threading.RLock()

    def _open(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self._restrict_parent:
            try:
                os.chmod(self.path.parent, 0o700)
            except OSError:
                pass
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        return connection

    def initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return
            with self._open() as connection:
                connection.execute("PRAGMA journal_mode = WAL")
                current = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if current not in {0, 1, 2, SCHEMA_VERSION}:
                    raise RuntimeError(f"unsupported database version: {current}")

                connection.execute("BEGIN IMMEDIATE")
                try:
                    self._create_profile_schema(connection)
                    if current < 2:
                        connection.execute(
                            """
                            UPDATE profile_facts
                            SET user_id = 'legacy:' || user_id
                            """
                        )
                    self._create_auth_schema(connection)
                    self._create_conversation_schema(connection)
                    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
            self._initialized = True

    def connect(self) -> sqlite3.Connection:
        self.initialize()
        return self._open()

    @staticmethod
    def _create_profile_schema(connection: sqlite3.Connection) -> None:
        connection.execute(
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
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_profile_facts_user_active
            ON profile_facts(user_id, superseded_at, expires_at)
            """
        )

    @staticmethod
    def _create_auth_schema(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                username_normalized TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                disabled_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_active
            ON auth_sessions(user_id, expires_at, revoked_at)
            """
        )

    @staticmethod
    def _create_conversation_schema(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_states (
                session_key_hash TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                revision INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversation_states_expiry
            ON conversation_states(expires_at)
            """
        )


@lru_cache(maxsize=1)
def get_database() -> SQLiteDatabase:
    return SQLiteDatabase()
