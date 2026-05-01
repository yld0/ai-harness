"""Request-scoped tool execution context (set by AgentRunner)."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai.agent.progress import NoopProgressSink, ProgressSink
from ai.agent.prompt_builder import Channel
from ai.tools.permissions import SessionPermissionT

_tool_ctx: ContextVar["ToolContext | None"] = ContextVar("tool_context", default=None)


@dataclass(frozen=True, slots=True)
class ToolContext:
    user_id: str
    session_id: str
    session_permission: SessionPermissionT
    channel: Channel
    route: str
    progress: ProgressSink
    bearer_token: str | None
    memory_root: Path
    project_root: Path
    request_id: str | None = None
    request_metadata: dict[str, Any] | None = None

    async def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        await self.progress.emit(event_type, payload)

    async def emit_cot(
        self,
        *,
        step_id: str,
        step_type: str,
        tool: str,
        label: str,
        status: str = "active",
    ) -> None:
        await self.progress.cot_step(
            step_id=step_id,
            step_type=step_type,
            title=label,
            status=status,
            tool=tool,
            label=label,
        )


def get_tool_context() -> ToolContext:
    """Return the current tool context (must be set for each agent request)."""
    value = _tool_ctx.get()
    if value is None:
        return ToolContext(
            user_id="anonymous",
            session_id="default",
            session_permission="ReadOnly",
            channel="web",
            route="",
            progress=NoopProgressSink(),
            bearer_token=None,
            memory_root=Path("./memory"),
            project_root=Path("."),
            request_id=None,
        )
    return value


def set_tool_context(ctx: ToolContext) -> object:
    return _tool_ctx.set(ctx)


def reset_tool_context(token: object) -> None:
    _tool_ctx.reset(token)
