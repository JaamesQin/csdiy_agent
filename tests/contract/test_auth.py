from __future__ import annotations

import pytest
from tests.conftest import ASGITestClient


@pytest.mark.parametrize(
    ("headers", "message"),
    [
        ({}, "Missing Authorization header"),
        ({"Authorization": "Bearer wrong-key"}, "Invalid API key"),
        ({"Authorization": "Basic abc"}, "Invalid Authorization header"),
        ({"Authorization": "Bearer"}, "Invalid Authorization header"),
        ({"Authorization": "Bearer "}, "Invalid Authorization header"),
    ],
)
def test_models_rejects_invalid_credentials(
    client: ASGITestClient, headers: dict[str, str], message: str
) -> None:
    response = client.get("/v1/models", headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["message"] == message


def test_chat_rejects_wrong_key_before_processing_body(client: ASGITestClient) -> None:
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer wrong-key"},
        json={"messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 401


def test_responses_do_not_leak_key(
    client: ASGITestClient, auth_headers: dict[str, str], api_key: str
) -> None:
    responses = [
        client.get("/v1/models", headers=auth_headers),
        client.post(
            "/v1/chat/completions",
            headers=auth_headers,
            json={"messages": [{"role": "user", "content": "hello"}]},
        ),
        client.get(
            "/v1/models",
            headers={"Authorization": "Bearer intentionally-wrong-key"},
        ),
    ]

    assert all(api_key not in response.text for response in responses)
