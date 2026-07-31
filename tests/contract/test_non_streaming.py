from __future__ import annotations

import re

import pytest
from tests.conftest import ASGITestClient


@pytest.mark.parametrize("model", [pytest.param(None, id="null"), ""])
def test_non_streaming_accepts_empty_or_null_model(
    client: ASGITestClient, auth_headers: dict[str, str], model: str | None
) -> None:
    response = client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={
            "model": model,
            "messages": [{"role": "user", "content": "你好"}],
            "stream": False,
            "max_tokens": 1,
        },
    )

    assert response.status_code == 200


def test_non_streaming_accepts_missing_model_and_stream(
    client: ASGITestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={
            "messages": [
                {"role": "system", "content": "测试系统提示"},
                {"role": "user", "content": "第一条"},
                {"role": "assistant", "content": "历史回复"},
                {"role": "user", "content": "最后一条"},
            ],
            "max_tokens": 1,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert re.fullmatch(r"chatcmpl-[0-9a-f]{32}", body["id"])
    assert body["object"] == "chat.completion"
    assert isinstance(body["created"], int)
    assert body["model"] == "coursepilot-probe"
    assert body["choices"] == [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "接入测试成功。收到用户消息：最后一条",
            },
            "finish_reason": "stop",
        }
    ]
    assert body["usage"] == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
