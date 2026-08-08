from __future__ import annotations

from tests.conftest import ASGITestClient
from tests.helpers import parse_sse


def test_streaming_contract(
    client: ASGITestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={
            "model": None,
            "messages": [{"role": "user", "content": "你好"}],
            "stream": True,
            "max_tokens": 1,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"

    events = parse_sse(response.text)
    assert events[-1] == "[DONE]"
    frames = [event for event in events if isinstance(event, dict)]

    role_frames = [
        frame for frame in frames if frame["choices"][0]["delta"].get("role")
    ]
    content_frames = [
        frame for frame in frames if "content" in frame["choices"][0]["delta"]
    ]
    stop_frames = [
        frame
        for frame in frames
        if frame["choices"][0]["finish_reason"] == "stop"
    ]

    assert len(role_frames) == 1
    assert frames[0] == role_frames[0]
    assert role_frames[0]["choices"][0]["delta"] == {"role": "assistant"}
    assert content_frames
    assert "".join(
        frame["choices"][0]["delta"]["content"] for frame in content_frames
    ) == (
        "你好，我是 CoursePilot。我可以先建立学习画像，或对你粘贴的代码做静态辅导。"
        "你想学习哪个 CS 方向？每周大约能投入多少时间？"
    )
    assert len(stop_frames) == 1
    assert frames[-1] == stop_frames[0]
    assert stop_frames[0]["choices"][0]["delta"] == {}
    assert stop_frames[0]["usage"] == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    assert events.count("[DONE]") == 1

    identifiers = {(frame["id"], frame["created"], frame["model"]) for frame in frames}
    assert len(identifiers) == 1
    assert all(
        frame["choices"][0]["finish_reason"] in {None, "stop"} for frame in frames
    )
