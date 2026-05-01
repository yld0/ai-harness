"""WebSocket non-token progress sequence (Phase 7)."""

import jwt

from fastapi.testclient import TestClient

from ai.main import app


def _token() -> str:
    return jwt.encode({"sub": "p7-user"}, "test-secret", algorithm="HS256")


def _drain_to_chat(ws) -> tuple[list[dict], dict]:
    out: list[dict] = []
    while True:
        msg = ws.receive_json()
        if msg.get("type") == "chat_response":
            return out, msg
        out.append(msg)


def test_ws_event_sequence_auth_cot_task_usage_final(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_SECRETPHRASE", "test-secret")
    with TestClient(app) as client:
        with client.websocket_connect("/v3/ws/p7-1") as ws:
            ws.send_json({"type": "authenticate", "token": _token()})
            assert ws.receive_json()["type"] == "auth_ok"
            ws.send_json(
                {
                    "type": "chat_request",
                    "data": {
                        "conversationID": "conv-p7",
                        "request": {"query": "WS sequence test"},
                        "context": {"route": "chats"},
                        "mode": "auto",
                    },
                }
            )
            events, final = _drain_to_chat(ws)

    labels = [e["type"] for e in events]
    assert labels[0] == "conversation_id"
    assert "task_progress" in labels
    assert labels.count("cot_step") >= 1
    assert "usage" in labels
    assert "task_progress_summary" in labels
    assert labels.index("usage") < labels.index("task_progress_summary")
    assert final["type"] == "chat_response"
    use = next(e for e in events if e["type"] == "usage")
    assert "model" in use["payload"] or "prompt_tokens" in use["payload"]
