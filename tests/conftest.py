from __future__ import annotations

import os
from typing import Any

import httpx
import pytest

TEST_API_KEY = "local-test-key-0123456789abcdef"
os.environ["COURSEPILOT_API_KEY"] = TEST_API_KEY
os.environ["COURSEPILOT_TEST_MODE"] = "true"

from app.main import app  # noqa: E402


class ASGITestClient:
    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.request(method, path, **kwargs)

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        import asyncio

        return asyncio.run(self._request("GET", path, **kwargs))

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        import asyncio

        return asyncio.run(self._request("POST", path, **kwargs))


@pytest.fixture
def api_key() -> str:
    return TEST_API_KEY


@pytest.fixture
def auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


@pytest.fixture
def client() -> ASGITestClient:
    return ASGITestClient()
