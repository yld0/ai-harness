import pytest
from fastapi.testclient import TestClient

from ai.main import app


def test_question_route_returns_agent_response(
    monkeypatch: pytest.MonkeyPatch,
    auth_env: None,
    auth_headers,
    chat_payload: dict,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v3/agent/question",
            headers=auth_headers(),
            json=chat_payload,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["conversationID"] == "conversation-1"
    assert body["response"]["text"].startswith("[stub]")
    assert body["metadata"]["user_id"] == "user-1"


def test_healthz_and_no_v2_registered() -> None:
    with TestClient(app) as client:
        health = client.get("/healthz")
        missing_v2 = client.post("/v2/agent/question", json={})

    assert health.status_code == 200
    assert health.json()["ok"] is True
    assert set(health.json()["deps"]) == {"graphql", "gemini", "openrouter", "fmp"}
    assert missing_v2.status_code == 404


def test_request_id_middleware_generates_and_echoes(
    auth_env: None,
    auth_headers,
    chat_payload: dict,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v3/agent/question",
            headers=auth_headers(),
            json=chat_payload,
        )
    assert response.status_code == 200
    rid = response.headers.get("X-Request-ID")
    assert rid is not None and len(rid) >= 8


def test_request_id_middleware_preserves_client_header(
    auth_env: None,
    auth_headers,
    chat_payload: dict,
) -> None:
    hdrs = auth_headers()
    hdrs["X-Request-ID"] = "client-correlation-abc"
    with TestClient(app) as client:
        response = client.post(
            "/v3/agent/question",
            headers=hdrs,
            json=chat_payload,
        )
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "client-correlation-abc"
