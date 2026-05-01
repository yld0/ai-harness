import jwt
from fastapi.testclient import TestClient

from ai.api.auth import decode_token
from ai.main import app


def token(payload: dict, secret: str = "test-secret") -> str:
    return jwt.encode(payload, secret, algorithm="HS256")


def test_decode_token_requires_sub(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_SECRETPHRASE", "test-secret")

    user = decode_token(token({"sub": "user-1"}))

    assert user.user_id == "user-1"


def test_http_rejects_missing_sub(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_SECRETPHRASE", "test-secret")

    with TestClient(app) as client:
        response = client.post(
            "/v3/agent/question",
            headers={"Authorization": f"Bearer {token({'email': 'x@example.com'})}"},
            json={
                "conversationID": "c-1",
                "request": {"query": "hello"},
                "context": {"route": "chats"},
            },
        )

    assert response.status_code == 401
    assert response.json() == {"error": {"code": "auth_invalid", "message": "JWT missing required sub claim"}}


def test_http_rejects_missing_bearer() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v3/agent/question",
            json={
                "conversationID": "c-1",
                "request": {"query": "hello"},
                "context": {"route": "chats"},
            },
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth_invalid"
