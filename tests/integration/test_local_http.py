from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from tests.conftest import TEST_API_KEY
from tests.helpers import parse_sse

ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def live_server_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["COURSEPILOT_API_KEY"] = TEST_API_KEY
    env["COURSEPILOT_TEST_MODE"] = "true"
    env["COURSEPILOT_DB_PATH"] = str(
        tmp_path_factory.mktemp("live-auth") / "coursepilot.sqlite3"
    )

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=2)
            pytest.fail(f"Uvicorn exited early.\nstdout={stdout}\nstderr={stderr}")
        try:
            if httpx.get(f"{url}/health", timeout=0.25).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.05)
    else:
        process.terminate()
        pytest.fail("Uvicorn did not become healthy within 10 seconds")

    yield url

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_API_KEY}"}


def test_live_auth_and_non_streaming(live_server_url: str) -> None:
    assert httpx.get(f"{live_server_url}/health").json() == {"status": "ok"}
    assert (
        httpx.get(
            f"{live_server_url}/v1/models",
            headers={"Authorization": "Bearer wrong-key"},
        ).status_code
        == 401
    )

    response = httpx.post(
        f"{live_server_url}/v1/chat/completions",
        headers=_headers(),
        json={
            "messages": [{"role": "user", "content": "/help"}],
            "stream": False,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    content = response.json()["choices"][0]["message"]["content"]
    assert "画像" in content
    assert "代码" in content


def test_live_account_session_and_profile(live_server_url: str) -> None:
    with httpx.Client(base_url=live_server_url) as client:
        registered = client.post(
            "/auth/register",
            headers={"Origin": live_server_url},
            json={
                "username": "LiveUser",
                "password": "correct-horse-battery",
            },
        )
        assert registered.status_code == 201
        csrf = registered.json()["csrf_token"]

        saved = client.post(
            "/v1/chat/completions",
            headers={"X-CSRF-Token": csrf},
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": "我想学习算法方向，每周 3 小时，而且有 Python 基础。",
                    }
                ]
            },
        )
        assert saved.status_code == 200
        assert "画像更新" in saved.json()["choices"][0]["message"]["content"]

        profile = client.post(
            "/v1/chat/completions",
            headers={"X-CSRF-Token": csrf},
            json={"messages": [{"role": "user", "content": "查看我的学习画像"}]},
        )
        assert profile.status_code == 200
        assert "180" in profile.json()["choices"][0]["message"]["content"]


def test_live_sse_headers_order_and_timing(live_server_url: str) -> None:
    arrival_times: list[float] = []
    lines: list[str] = []
    start = time.monotonic()

    with httpx.stream(
        "POST",
        f"{live_server_url}/v1/chat/completions",
        headers=_headers(),
        json={
            "messages": [{"role": "user", "content": "真实流式测试"}],
            "stream": True,
        },
        timeout=5,
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        for line in response.iter_lines():
            if line.startswith("data: "):
                lines.append(line)
                arrival_times.append(time.monotonic() - start)

    events = parse_sse("\n\n".join(lines) + "\n\n")
    assert events[-1] == "[DONE]"
    assert len(arrival_times) >= 4
    assert arrival_times[-1] > arrival_times[0]


@pytest.mark.asyncio
async def test_light_concurrency_and_repetition(live_server_url: str) -> None:
    async with httpx.AsyncClient(timeout=5) as client:
        model_responses = await asyncio.gather(
            *[
                client.get(f"{live_server_url}/v1/models", headers=_headers())
                for _ in range(100)
            ]
        )
        non_streaming = await asyncio.gather(
            *[
                client.post(
                    f"{live_server_url}/v1/chat/completions",
                    headers=_headers(),
                    json={
                        "messages": [{"role": "user", "content": f"request-{index}"}],
                        "stream": False,
                    },
                )
                for index in range(100)
            ]
        )
        streaming = await asyncio.gather(
            *[
                client.post(
                    f"{live_server_url}/v1/chat/completions",
                    headers=_headers(),
                    json={
                        "messages": [{"role": "user", "content": f"stream-{index}"}],
                        "stream": True,
                    },
                )
                for index in range(20)
            ]
        )

    assert all(response.status_code == 200 for response in model_responses)
    assert all(response.status_code == 200 for response in non_streaming)
    assert all(response.status_code == 200 for response in streaming)
    assert all(response.text.rstrip().endswith("data: [DONE]") for response in streaming)
