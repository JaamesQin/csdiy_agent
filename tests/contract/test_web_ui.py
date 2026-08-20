from __future__ import annotations

import re

from tests.conftest import ASGITestClient


def test_chat_page_is_available(client: ASGITestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-cache"
    assert "CoursePilot" in response.text
    assert "登录" in response.text
    assert '<div id="root"></div>' in response.text
    assert response.headers["x-frame-options"] == "DENY"
    csp = response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in csp
    assert "script-src 'self'" in csp
    assert "style-src 'self'" in csp
    assert "unsafe-inline" not in csp


def test_chat_assets_are_available(client: ASGITestClient) -> None:
    page = client.get("/").text
    assets = set(
        re.findall(
            r'<(?:script|link)\b[^>]*(?:src|href)="([^"]+)"',
            page,
        )
    )

    assert any(path.endswith(".css") for path in assets)
    assert any(path.endswith(".js") for path in assets)
    assert all(path.startswith("/static/") for path in assets)
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", page)
    assert "<style" not in page

    for path in assets:
        response = client.get(path)
        assert response.status_code == 200, path
        if path.endswith(".css"):
            assert response.headers["content-type"].startswith("text/css")
        elif path.endswith(".js"):
            assert "javascript" in response.headers["content-type"]
        elif path.endswith(".svg"):
            assert response.headers["content-type"].startswith("image/svg+xml")

    favicon = client.get("/favicon.ico")
    assert favicon.status_code == 200
    assert favicon.headers["content-type"].startswith("image/svg+xml")
