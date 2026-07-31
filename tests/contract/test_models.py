from __future__ import annotations

from tests.conftest import ASGITestClient


def test_health_is_public(client: ASGITestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_models_returns_openai_list(
    client: ASGITestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/v1/models", headers=auth_headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "object": "list",
        "data": [
            {
                "id": "coursepilot-probe",
                "object": "model",
                "owned_by": "coursepilot",
            }
        ],
    }
