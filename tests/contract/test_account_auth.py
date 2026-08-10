from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from app.auth.repository import SQLiteAuthRepository
from app.auth.service import AuthService, get_auth_service
from app.main import app
from app.profile.repository import SQLiteProfileRepository
from app.profile.service import ProfileService, get_profile_service
from app.storage.database import SQLiteDatabase
from tests.conftest import ASGITestClient


@dataclass(frozen=True)
class AccountServices:
    auth: AuthService
    profiles: ProfileService
    database: SQLiteDatabase


@pytest.fixture
def account_services(tmp_path) -> Iterator[AccountServices]:
    database = SQLiteDatabase(tmp_path / "coursepilot.sqlite3")
    auth = AuthService(
        SQLiteAuthRepository(database),
        secret="test-auth-secret-0123456789",
    )
    profiles = ProfileService(SQLiteProfileRepository(database))
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.dependency_overrides[get_profile_service] = lambda: profiles
    try:
        yield AccountServices(auth=auth, profiles=profiles, database=database)
    finally:
        app.dependency_overrides.pop(get_auth_service, None)
        app.dependency_overrides.pop(get_profile_service, None)


def _register(client: ASGITestClient, username: str) -> tuple[str, str, dict[str, object]]:
    response = client.post(
        "/auth/register",
        headers={"Origin": "http://testserver"},
        json={"username": username, "password": "correct-horse-battery"},
    )
    assert response.status_code == 201
    return (
        response.cookies["coursepilot_session"],
        response.json()["csrf_token"],
        response.json()["user"],
    )


def test_register_me_login_logout_and_cookie_security(
    client: ASGITestClient, account_services: AccountServices
) -> None:
    token, csrf, user = _register(client, "Alice")
    cookie_header = client.post(
        "/auth/register",
        headers={"Origin": "http://testserver"},
        json={"username": "Bob", "password": "correct-horse-battery"},
    ).headers["set-cookie"].lower()
    assert "httponly" in cookie_header
    assert "samesite=strict" in cookie_header
    assert "path=/" in cookie_header
    assert "max-age" not in cookie_header
    assert "domain=" not in cookie_header

    me = client.get(
        "/auth/me", headers={"Cookie": f"coursepilot_session={token}"}
    )
    assert me.status_code == 200
    assert me.json()["user"] == user
    assert me.headers["cache-control"] == "no-store"
    assert client.get(
        "/v1/models", headers={"Cookie": f"coursepilot_session={token}"}
    ).status_code == 200

    wrong_logout = client.post(
        "/auth/logout",
        headers={
            "Cookie": f"coursepilot_session={token}",
            "X-CSRF-Token": "wrong",
            "Origin": "http://testserver",
        },
    )
    assert wrong_logout.status_code == 403

    logout = client.post(
        "/auth/logout",
        headers={
            "Cookie": f"coursepilot_session={token}",
            "X-CSRF-Token": csrf,
            "Origin": "http://testserver",
        },
    )
    assert logout.status_code == 204
    assert client.get(
        "/auth/me", headers={"Cookie": f"coursepilot_session={token}"}
    ).status_code == 401

    login = client.post(
        "/auth/login",
        headers={"Origin": "http://testserver"},
        json={"username": "alice", "password": "correct-horse-battery"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["username"] == "Alice"


def test_duplicate_login_errors_origin_and_rate_limit(
    client: ASGITestClient, account_services: AccountServices
) -> None:
    _register(client, "Alice")
    duplicate = client.post(
        "/auth/register",
        json={"username": "alice", "password": "correct-horse-battery"},
    )
    assert duplicate.status_code == 409

    missing = client.post(
        "/auth/login",
        json={"username": "Missing", "password": "incorrect-password-value"},
    )
    wrong = client.post(
        "/auth/login",
        json={"username": "Alice", "password": "incorrect-password-value"},
    )
    assert missing.status_code == wrong.status_code == 401
    assert missing.json()["error"]["message"] == wrong.json()["error"]["message"]

    cross_origin = client.post(
        "/auth/login",
        headers={"Origin": "https://evil.example"},
        json={"username": "Alice", "password": "correct-horse-battery"},
    )
    assert cross_origin.status_code == 403

    for _ in range(4):
        client.post(
            "/auth/login",
            json={"username": "Alice", "password": "incorrect-password-value"},
        )
    limited = client.post(
        "/auth/login",
        json={"username": "Alice", "password": "incorrect-password-value"},
    )
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) > 0


def test_account_profiles_are_isolated_and_body_user_cannot_spoof(
    client: ASGITestClient,
    auth_headers: dict[str, str],
    account_services: AccountServices,
) -> None:
    alice_token, alice_csrf, alice = _register(client, "Alice")
    bob_token, bob_csrf, bob = _register(client, "Bob")

    saved = client.post(
        "/v1/chat/completions",
        headers={
            "Cookie": f"coursepilot_session={alice_token}",
            "X-CSRF-Token": alice_csrf,
        },
        json={
            "user": f"account:{bob['id']}",
            "messages": [
                {
                    "role": "user",
                    "content": "我想学习系统方向，每周可以投入 6 小时，而且有 Python 基础。",
                }
            ],
        },
    )
    assert saved.status_code == 200
    assert "画像更新" in saved.json()["choices"][0]["message"]["content"]

    alice_profile = client.post(
        "/v1/chat/completions",
        headers={
            "Cookie": f"coursepilot_session={alice_token}",
            "X-CSRF-Token": alice_csrf,
        },
        json={"messages": [{"role": "user", "content": "查看我的学习画像"}]},
    )
    bob_profile = client.post(
        "/v1/chat/completions",
        headers={
            "Cookie": f"coursepilot_session={bob_token}",
            "X-CSRF-Token": bob_csrf,
        },
        json={"messages": [{"role": "user", "content": "查看我的学习画像"}]},
    )
    assert "360" in alice_profile.json()["choices"][0]["message"]["content"]
    assert "当前没有" in bob_profile.json()["choices"][0]["message"]["content"]

    legacy_probe = client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={
            "user": f"account:{alice['id']}",
            "messages": [{"role": "user", "content": "查看我的学习画像"}],
        },
    )
    assert "当前没有" in legacy_probe.json()["choices"][0]["message"]["content"]

    legacy_saved = client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={
            "user": "legacy-a",
            "messages": [
                {
                    "role": "user",
                    "content": "我想学习算法方向，每周 2 小时。",
                }
            ],
        },
    )
    assert "画像更新" in legacy_saved.json()["choices"][0]["message"]["content"]
    legacy_same = client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={
            "user": "legacy-a",
            "messages": [{"role": "user", "content": "查看我的学习画像"}],
        },
    )
    legacy_other = client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={
            "user": "legacy-b",
            "messages": [{"role": "user", "content": "查看我的学习画像"}],
        },
    )
    assert "120" in legacy_same.json()["choices"][0]["message"]["content"]
    assert "当前没有" in legacy_other.json()["choices"][0]["message"]["content"]


def test_cookie_chat_requires_csrf_but_api_key_does_not(
    client: ASGITestClient,
    auth_headers: dict[str, str],
    account_services: AccountServices,
) -> None:
    token, _, _ = _register(client, "Alice")
    cookie_response = client.post(
        "/v1/chat/completions",
        headers={"Cookie": f"coursepilot_session={token}"},
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert cookie_response.status_code == 403

    api_key_response = client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert api_key_response.status_code == 200
