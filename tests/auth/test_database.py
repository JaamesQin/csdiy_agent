from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.auth.repository import DuplicateUsernameError, SQLiteAuthRepository
from app.profile.repository import SQLiteProfileRepository
from app.storage.database import SCHEMA_VERSION, SQLiteDatabase


def test_empty_database_initializes_v2(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "coursepilot.sqlite3")
    database.initialize()

    with database.connect() as connection:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert version == SCHEMA_VERSION
    assert {"users", "auth_sessions", "profile_facts"} <= tables


def test_v1_profile_database_is_migrated_to_legacy_namespace(tmp_path) -> None:
    path = tmp_path / "profiles.sqlite3"
    with sqlite3.connect(path) as connection:
        SQLiteDatabase._create_profile_schema(connection)
        connection.execute(
            """
            INSERT INTO profile_facts (
                id, user_id, field_name, value_json, status, confidence,
                evidence_excerpt, created_at
            ) VALUES ('fact-1', 'old-user', 'background', '"Python"',
                      'confirmed', 1.0, 'Python', '2026-08-09T00:00:00+00:00')
            """
        )
        connection.execute(
            """
            INSERT INTO profile_facts (
                id, user_id, field_name, value_json, status, confidence,
                evidence_excerpt, created_at
            ) VALUES ('fact-2', 'account:spoofed', 'background', '"Rust"',
                      'confirmed', 1.0, 'Rust', '2026-08-09T00:00:01+00:00')
            """
        )
        connection.execute("PRAGMA user_version = 1")

    database = SQLiteDatabase(path)
    database.initialize()

    with database.connect() as connection:
        row = connection.execute(
            "SELECT user_id FROM profile_facts WHERE id = 'fact-1'"
        ).fetchone()
        spoofed = connection.execute(
            "SELECT user_id FROM profile_facts WHERE id = 'fact-2'"
        ).fetchone()
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])

    assert row["user_id"] == "legacy:old-user"
    assert spoofed["user_id"] == "legacy:account:spoofed"
    assert SQLiteProfileRepository(database).get_profile("legacy:old-user") == {
        "background": ["Python"]
    }
    assert version == SCHEMA_VERSION


def test_unknown_database_version_is_rejected(tmp_path) -> None:
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 99")

    with pytest.raises(RuntimeError, match="unsupported database version"):
        SQLiteDatabase(path).initialize()


def test_concurrent_duplicate_registration_has_one_winner(tmp_path) -> None:
    repository = SQLiteAuthRepository(SQLiteDatabase(tmp_path / "accounts.sqlite3"))

    def create(_: int) -> str:
        try:
            return repository.create_user(
                username="Alice",
                username_normalized="alice",
                password_hash="$argon2id$test",
            ).id
        except DuplicateUsernameError:
            return "duplicate"

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(create, range(12)))

    assert len([result for result in results if result != "duplicate"]) == 1
    assert results.count("duplicate") == 11
