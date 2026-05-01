"""WebSocket wire helpers: event shapes for progress streaming (Phase 7)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """One server→client progress frame: { type, payload }."""
    return {"type": event_type, "payload": payload}


def auth_ok_message() -> dict[str, Any]:
    return {"type": "auth_ok", "message": "Authenticated"}


def auth_ok_legacy_alias() -> dict[str, Any]:
    """Optional legacy `authentication` name (same body style as WsAuthResponse)."""
    return {"type": "authentication", "message": "Authenticated"}


def conversation_id_event(conversation_id: str) -> dict[str, Any]:
    return event("conversation_id", {"conversation_id": conversation_id})


def cot_step_payload(
    *,
    step_id: str,
    step_type: str,
    label: str,
    tool: str | None = None,
    ts: str | None = None,
) -> dict[str, Any]:
    """CotStep-style payload (short strings; `step_type` matches plan table)."""
    body: dict[str, Any] = {
        "id": step_id,
        "step_type": step_type,
        "label": label,
        "ts": ts or utc_ts(),
    }
    if tool is not None:
        body["tool"] = tool
    return body


def task_progress_event(
    *,
    task_id: str,
    title: str,
    items: list[dict[str, Any]],
    default_open: bool = True,
) -> dict[str, Any]:
    return event(
        "task_progress",
        {
            "task_id": task_id,
            "title": title,
            "items": items,
            "default_open": default_open,
        },
    )


def task_progress_summary_event(*, task_id: str, summary: str) -> dict[str, Any]:
    return event("task_progress_summary", {"task_id": task_id, "summary": summary})


def usage_event(
    *,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    model: str | None = None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "model": model,
    }
    if raw:
        payload["raw"] = raw
    return event("usage", {k: v for k, v in payload.items() if v is not None or k == "raw"})


def error_event(*, code: str, message: str, retryable: bool = False) -> dict[str, Any]:
    return event("error", {"code": code, "message": message, "retryable": retryable})


def chat_response_event(data: dict[str, Any]) -> dict[str, Any]:
    return {"type": "chat_response", "data": data}
