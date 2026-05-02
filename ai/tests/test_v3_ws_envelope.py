import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from ai.main import app


def token(user_id: str = "user-1") -> str:
    return jwt.encode({"sub": user_id}, "test-secret", algorithm="HS256")


def ws_payload(conversation_id: str = "ws-conversation", query: str = "Hello over websocket") -> dict:
    return {
        "type": "chat_request",
        "data": {
            "conversationID": conversation_id,
            "request": {"query": query},
            "context": {"route": "chats"},
            "mode": "auto",
        },
    }


def _collect_until_chat(ws) -> tuple[list[dict], dict]:
    events: list[dict] = []
    while True:
        msg = ws.receive_json()
        if msg.get("type") == "chat_response":
            return events, msg
        events.append(msg)


def test_websocket_auth_via_first_message(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_SECRETPHRASE", "test-secret")

    with TestClient(app) as client:
        with client.websocket_connect("/v3/ws/client-1") as websocket:
            websocket.send_json({"type": "authenticate", "token": token("user-1")})
            assert websocket.receive_json() == {
                "type": "auth_ok",
                "payload": {"message": "Authenticated"},
            }

            websocket.send_json(ws_payload())
            events, final = _collect_until_chat(websocket)

    assert events[0]["type"] == "conversation_id"
    assert events[0]["payload"]["conversation_id"] == "ws-conversation"
    assert events[1]["type"] == "task_progress"
    types = [e["type"] for e in events]
    assert "cot_step" in types
    assert "usage" in types
    assert "task_progress_summary" in types
    assert types.index("usage") < types.index("task_progress_summary")
    assert final["type"] == "chat_response"
    assert final["payload"]["data"]["conversationID"] == "ws-conversation"
    assert final["payload"]["data"]["metadata"]["user_id"] == "user-1"


def test_websocket_auth_via_header(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_SECRETPHRASE", "test-secret")

    with TestClient(app) as client:
        with client.websocket_connect(
            "/v3/ws/client-2",
            headers={"Authorization": f"Bearer {token('user-2')}"},
        ) as websocket:
            websocket.send_json(ws_payload())
            events, final = _collect_until_chat(websocket)

    assert events[0]["type"] == "conversation_id"
    assert "cot_step" in [e["type"] for e in events]
    assert final["type"] == "chat_response"
    assert final["payload"]["data"]["metadata"]["user_id"] == "user-2"


def test_websocket_reuses_first_message_auth_for_multiple_turns(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_SECRETPHRASE", "test-secret")

    with TestClient(app) as client:
        with client.websocket_connect("/v3/ws/client-multiturn") as websocket:
            websocket.send_json({"type": "authenticate", "token": token("user-1")})
            assert websocket.receive_json()["type"] == "auth_ok"

            websocket.send_json(ws_payload("ws-conversation-1", "First message"))
            _, first = _collect_until_chat(websocket)

            websocket.send_json(ws_payload("ws-conversation-2", "Second message"))
            _, second = _collect_until_chat(websocket)

    assert first["type"] == "chat_response"
    assert first["payload"]["data"]["conversationID"] == "ws-conversation-1"
    assert first["payload"]["data"]["metadata"]["user_id"] == "user-1"
    assert second["type"] == "chat_response"
    assert second["payload"]["data"]["conversationID"] == "ws-conversation-2"
    assert second["payload"]["data"]["metadata"]["user_id"] == "user-1"


def test_websocket_allows_valid_auth_after_consecutive_auth_failures(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_SECRETPHRASE", "test-secret")

    with TestClient(app) as client:
        with client.websocket_connect("/v3/ws/client-auth-retry") as websocket:
            for _ in range(4):
                websocket.send_json({"type": "chat_request"})
                assert websocket.receive_json() == {
                    "error": {
                        "code": "auth_invalid",
                        "message": "First message must authenticate",
                    }
                }

            websocket.send_json({"type": "authenticate", "token": token("user-1")})
            assert websocket.receive_json()["type"] == "auth_ok"

            websocket.send_json(ws_payload())
            _, final = _collect_until_chat(websocket)

    assert final["type"] == "chat_response"
    assert final["payload"]["data"]["metadata"]["user_id"] == "user-1"


def test_websocket_closes_after_bad_post_auth_message(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_SECRETPHRASE", "test-secret")

    with TestClient(app) as client:
        with pytest.raises(ValidationError):
            with client.websocket_connect("/v3/ws/client-bad-envelope") as websocket:
                websocket.send_json({"type": "authenticate", "token": token("user-1")})
                assert websocket.receive_json()["type"] == "auth_ok"
                websocket.send_json({"type": "authenticate", "token": token("user-1")})
                websocket.receive_json()


def test_websocket_closes_after_max_first_message_auth_failures(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_SECRETPHRASE", "test-secret")

    with TestClient(app) as client:
        with client.websocket_connect("/v3/ws/client-3") as websocket:
            for _ in range(5):
                websocket.send_json({"type": "chat_request"})
                error = websocket.receive_json()
            with pytest.raises(WebSocketDisconnect) as exc_info:
                websocket.receive_json()

    assert error == {
        "error": {
            "code": "auth_invalid",
            "message": "First message must authenticate",
        }
    }
    assert exc_info.value.code == 4401
