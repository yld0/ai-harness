"""Progress event sinks: generic `emit` plus CoT convenience (Phase 7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ai.api.send import cot_step_payload, event


@runtime_checkable
class ProgressSink(Protocol):
    async def emit(self, event_type: str, payload: dict[str, Any]) -> None: ...

    async def cot_step(
        self,
        *,
        step_id: str,
        step_type: str,
        title: str,
        status: str = "complete",
        content: str | None = None,
        tool: str | None = None,
        label: str | None = None,
    ) -> None: ...


class NullProgressSink:
    """HTTP and paths that ignore streaming."""

    async def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        return None

    async def cot_step(
        self,
        *,
        step_id: str,
        step_type: str,
        title: str,
        status: str = "complete",
        content: str | None = None,
        tool: str | None = None,
        label: str | None = None,
    ) -> None:
        await _emit_cot_step(
            self,
            step_id=step_id,
            step_type=step_type,
            title=title,
            status=status,
            content=content,
            tool=tool,
            label=label,
        )


# Back-compat alias
NoopProgressSink = NullProgressSink


@dataclass
class CollectingProgressSink:
    """Records full `{type, payload}` frames (and chat_response) for WebSocket send."""

    events: list[dict[str, Any]] = field(default_factory=list)

    async def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append(event(event_type, payload))

    async def cot_step(
        self,
        *,
        step_id: str,
        step_type: str,
        title: str,
        status: str = "complete",
        content: str | None = None,
        tool: str | None = None,
        label: str | None = None,
    ) -> None:
        await _emit_cot_step(
            self,
            step_id=step_id,
            step_type=step_type,
            title=title,
            status=status,
            content=content,
            tool=tool,
            label=label,
        )


async def _emit_cot_step(
    sink: ProgressSink,
    *,
    step_id: str,
    step_type: str,
    title: str,
    status: str = "complete",
    content: str | None = None,
    tool: str | None = None,
    label: str | None = None,
) -> None:
    text = label or title
    payload = cot_step_payload(step_id=step_id, step_type=step_type, label=text, tool=tool)
    if content is not None:
        payload["content"] = content
    payload["status"] = status
    await sink.emit("cot_step", payload)
