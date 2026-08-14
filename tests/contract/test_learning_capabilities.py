from __future__ import annotations

import pytest

from tests.conftest import ASGITestClient
from tests.helpers import parse_sse


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("推荐一门深度学习课程", "在线 StudyKit：可用"),
        ("查看 MIT 6.7960 第 2 讲的 StudyKit", "practice-concept-01"),
        ("MIT 6.7960 第 2 讲的讲义里，反向传播和梯度下降有什么区别？", "不补充外部事实"),
        ("解释 MIT 6.7960 第 2 讲的反向传播", "**定义**"),
        ("给我一道 MIT 6.7960 第 2 讲的调试练习", "practice-debugging-01"),
        (
            "点评 MIT 6.7960 第 2 讲的 practice-concept-01。"
            "我的答案是反向传播计算梯度，梯度下降更新参数。",
            "不会对这次答案做不可靠判分",
        ),
    ],
)
def test_learning_capabilities_keep_non_streaming_envelope(
    client: ASGITestClient,
    auth_headers: dict[str, str],
    prompt: str,
    expected: str,
) -> None:
    response = client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={
            "model": "coursepilot-probe",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "coursepilot-probe"
    assert body["choices"][0]["finish_reason"] == "stop"
    assert expected in body["choices"][0]["message"]["content"]


def test_learning_capability_keeps_sse_order(
    client: ASGITestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={
            "messages": [
                {"role": "user", "content": "解释 MIT 6.7960 第 2 讲的反向传播"}
            ],
            "stream": True,
        },
    )

    events = parse_sse(response.text)
    frames = [event for event in events if isinstance(event, dict)]
    assert events[-1] == "[DONE]"
    assert frames[0]["choices"][0]["delta"] == {"role": "assistant"}
    assert sum(frame["choices"][0]["finish_reason"] == "stop" for frame in frames) == 1
    assert frames[-1]["choices"][0]["finish_reason"] == "stop"
    content = "".join(
        frame["choices"][0]["delta"].get("content", "") for frame in frames
    )
    assert "**定义**" in content
