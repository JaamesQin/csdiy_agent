from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from argon2 import PasswordHasher, Type

from app.auth.repository import SQLiteAuthRepository
from app.auth.service import AuthRateLimitError, AuthService, InvalidCredentialsError
from app.storage.database import SQLiteDatabase


def _service(tmp_path) -> tuple[AuthService, SQLiteDatabase]:
    database = SQLiteDatabase(tmp_path / "accounts.sqlite3")
    return (
        AuthService(
            SQLiteAuthRepository(database),
            secret="test-auth-secret-0123456789",
        ),
        database,
    )


def test_password_and_session_tokens_are_not_stored_in_plaintext(tmp_path) -> None:
    service, database = _service(tmp_path)
    password = "correct-horse-battery"
    session = service.register(
        username="Alice",
        password=password,
        client_key="127.0.0.1",
    )

    with database.connect() as connection:
        user = connection.execute("SELECT password_hash FROM users").fetchone()
        stored_session = connection.execute(
            "SELECT token_hash FROM auth_sessions"
        ).fetchone()

    assert user["password_hash"].startswith("$argon2id$")
    assert password not in user["password_hash"]
    assert stored_session["token_hash"] != session.token
    assert session.token not in database.path.read_bytes().decode("utf-8", errors="ignore")


def test_login_is_case_insensitive_and_errors_are_generic(tmp_path) -> None:
    service, _ = _service(tmp_path)
    service.register(
        username="Alice",
        password="correct-horse-battery",
        client_key="register",
    )

    logged_in = service.login(
        username="alice",
        password="correct-horse-battery",
        client_key="login",
    )
    assert logged_in.user.username == "Alice"

    with pytest.raises(InvalidCredentialsError, match="Invalid username or password"):
        service.login(
            username="missing",
            password="incorrect-password-value",
            client_key="login",
        )


def test_old_argon_parameters_are_rehashed_on_login(tmp_path) -> None:
    service, database = _service(tmp_path)
    old_hasher = PasswordHasher(
        time_cost=1,
        memory_cost=8192,
        parallelism=1,
        hash_len=16,
        salt_len=16,
        type=Type.ID,
    )
    old_hash = old_hasher.hash("correct-horse-battery")
    user = service.repository.create_user(
        username="Alice",
        username_normalized="alice",
        password_hash=old_hash,
    )

    service.login(
        username="Alice",
        password="correct-horse-battery",
        client_key="login",
    )

    updated = service.repository.get_user_by_normalized("alice")
    assert updated is not None
    assert updated.id == user.id
    assert updated.password_hash != old_hash
    assert service.password_hasher.verify(updated.password_hash, "correct-horse-battery")


def test_expired_revoked_and_cascaded_sessions_are_invalid(tmp_path) -> None:
    service, database = _service(tmp_path)
    session = service.register(
        username="Alice",
        password="correct-horse-battery",
        client_key="register",
    )
    assert service.authenticate(session.token) is not None

    service.logout(session.token)
    assert service.authenticate(session.token) is None

    second = service.login(
        username="Alice",
        password="correct-horse-battery",
        client_key="login",
    )
    with database.connect() as connection:
        connection.execute(
            "UPDATE auth_sessions SET expires_at = ?",
            ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(),),
        )
    assert service.authenticate(second.token) is None

    third = service.login(
        username="Alice",
        password="correct-horse-battery",
        client_key="login",
    )
    service.repository.delete_user(third.user.id)
    with database.connect() as connection:
        count = int(connection.execute("SELECT COUNT(*) FROM auth_sessions").fetchone()[0])
    assert count == 0


def test_failed_login_is_rate_limited(tmp_path) -> None:
    service, _ = _service(tmp_path)
    service.register(
        username="Alice",
        password="correct-horse-battery",
        client_key="register",
    )
    for _ in range(5):
        with pytest.raises(InvalidCredentialsError):
            service.login(
                username="Alice",
                password="incorrect-password-value",
                client_key="attacker",
            )

    with pytest.raises(AuthRateLimitError) as exc_info:
        service.login(
            username="Alice",
            password="incorrect-password-value",
            client_key="attacker",
        )
    assert exc_info.value.retry_after > 0
