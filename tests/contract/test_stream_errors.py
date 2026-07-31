from __future__ import annotations

from tests.conftest import ASGITestClient
from tests.helpers import parse_sse


def test_midstream_error_closes_protocol_cleanly(
    client: ASGITestClient, auth_headers: dict[str, str], api_key: str
) -> None:
    response = client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={
            "messages": [
                {"role": "user", "content": "__trigger_stream_error__"}
            ],
            "stream": True,
        },
    )

    assert response.status_code == 200
    events = parse_sse(response.text)
    assert events[-1] == "[DONE]"
    assert events.count("[DONE]") == 1

    frames = [event for event in events if isinstance(event, dict)]
    stop_frames = [
        frame
        for frame in frames
        if frame["choices"][0]["finish_reason"] == "stop"
    ]
    assert len(stop_frames) == 1
    stop = stop_frames[0]
    assert stop["error"]["type"] == "stream_error"
    assert stop["choices"][0]["finish_reason"] == "stop"
    assert "traceback" not in response.text.lower()
    assert "injected stream failure" not in response.text
    assert api_key not in response.text
