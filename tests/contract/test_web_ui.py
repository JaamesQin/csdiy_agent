from __future__ import annotations

from tests.conftest import ASGITestClient


def test_chat_page_is_available(client: ASGITestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "CoursePilot" in response.text
    assert "/v1/chat/completions" in response.text
    assert "登录" in response.text
    assert "注册" in response.text
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_chat_assets_are_available(client: ASGITestClient) -> None:
    stylesheet = client.get("/static/styles.css")
    script = client.get("/static/app.js")
    favicon = client.get("/favicon.ico")

    assert stylesheet.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert script.status_code == 200
    assert "readStream" in script.text
    assert 'fetch("/auth/me"' in script.text
    assert "X-CSRF-Token" in script.text
    assert "elements.loginForm.reset()" in script.text
    assert "elements.registerForm.reset()" in script.text
    assert "event.currentTarget.reset()" not in script.text
    assert 'sessionStorage.setItem("coursepilot_api_key"' not in script.text
    assert 'localStorage.setItem("coursepilot_anonymous_user"' not in script.text
    assert "静态代码辅导" in client.get("/").text
    assert favicon.status_code == 200
    assert favicon.headers["content-type"].startswith("image/svg+xml")
