from __future__ import annotations

from tests.conftest import ASGITestClient


def test_chat_page_is_available(client: ASGITestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "CoursePilot" in response.text
    assert "/v1/chat/completions" in response.text


def test_chat_assets_are_available(client: ASGITestClient) -> None:
    stylesheet = client.get("/static/styles.css")
    script = client.get("/static/app.js")
    favicon = client.get("/favicon.ico")

    assert stylesheet.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert script.status_code == 200
    assert "readStream" in script.text
    assert "coursepilot_anonymous_user" in script.text
    assert "user: state.userId" in script.text
    assert "静态代码辅导" in client.get("/").text
    assert favicon.status_code == 200
    assert favicon.headers["content-type"].startswith("image/svg+xml")
