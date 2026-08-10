from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.agent.contracts import AgentReply
from app.agent.runtime import get_coursepilot_agent
from app.main import app
from app.protocol.schemas import ChatMessage
from tests.conftest import ASGITestClient
from tests.helpers import parse_sse


class CapturingAgent:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.user_id: str | None = None
        self.messages: list[ChatMessage] = []

    async def handle(
        self, *, messages: list[ChatMessage], user_id: str | None
    ) -> AgentReply:
        if self.fail:
            raise RuntimeError("secret internal failure")
        self.user_id = user_id
        self.messages = messages
        return AgentReply(
            answer="测试 Agent 回复",
            usage={"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
        )


@pytest.fixture
def override_agent() -> Iterator[CapturingAgent]:
    agent = CapturingAgent()
    app.dependency_overrides[get_coursepilot_agent] = lambda: agent
    try:
        yield agent
    finally:
        app.dependency_overrides.pop(get_coursepilot_agent, None)


def test_optional_user_reaches_agent_without_changing_envelope(
    client: ASGITestClient,
    auth_headers: dict[str, str],
    override_agent: CapturingAgent,
) -> None:
    response = client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "user": "opaque-local-user",
        },
    )

    assert response.status_code == 200
    assert override_agent.user_id == "legacy:opaque-local-user"
    assert response.json()["choices"][0]["message"]["content"] == "测试 Agent 回复"
    assert response.json()["usage"]["total_tokens"] == 10


def test_agent_usage_is_forwarded_to_stream_stop_frame(
    client: ASGITestClient,
    auth_headers: dict[str, str],
    override_agent: CapturingAgent,
) -> None:
    response = client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
        },
    )

    frames = [event for event in parse_sse(response.text) if isinstance(event, dict)]
    assert frames[-1]["usage"] == {
        "prompt_tokens": 7,
        "completion_tokens": 3,
        "total_tokens": 10,
    }


def test_unhandled_agent_error_is_sanitized(
    client: ASGITestClient, auth_headers: dict[str, str]
) -> None:
    failing = CapturingAgent(fail=True)
    app.dependency_overrides[get_coursepilot_agent] = lambda: failing
    try:
        response = client.post(
            "/v1/chat/completions",
            headers=auth_headers,
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
    finally:
        app.dependency_overrides.pop(get_coursepilot_agent, None)

    assert response.status_code == 500
    assert response.json()["error"]["type"] == "server_error"
    assert "secret internal failure" not in response.text
