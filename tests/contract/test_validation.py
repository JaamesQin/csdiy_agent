from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.protocol.schemas import ChatCompletionRequest
from tests.conftest import ASGITestClient


@pytest.mark.parametrize("stream", ["false", "true", 0, 1, None, [], {}])
def test_stream_requires_a_json_boolean(
    client: ASGITestClient, auth_headers: dict[str, str], stream: object
) -> None:
    response = client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "stream": stream,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["type"] == "invalid_request_error"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"messages": []},
        {"messages": "not-a-list"},
        {"messages": [{"content": "missing role"}]},
        {"messages": [{"role": "user"}]},
        {"messages": [{"role": "tool", "content": "unsupported"}]},
        {"messages": [{"role": "assistant", "content": "no user message"}]},
    ],
)
def test_invalid_messages_return_422(
    client: ASGITestClient,
    auth_headers: dict[str, str],
    payload: dict[str, object],
) -> None:
    response = client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["error"]["type"] == "invalid_request_error"


def test_invalid_json_returns_422(
    client: ASGITestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/v1/chat/completions",
        headers={**auth_headers, "Content-Type": "application/json"},
        content="{not-json",
    )

    assert response.status_code == 422


def test_optional_openai_user_remains_backward_compatible() -> None:
    request = ChatCompletionRequest.model_validate(
        {
            "messages": [{"role": "user", "content": "hello"}],
            "user": "legacy-client-user",
        }
    )
    assert request.user == "legacy-client-user"

    with pytest.raises(ValidationError):
        ChatCompletionRequest.model_validate(
            {
                "messages": [{"role": "user", "content": "hello"}],
                "user": "x" * 129,
            }
        )
