from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from ai.agent.prompt_builder import Channel
from ai.tools.filesystem.permissions import SessionPermissionT
from ai.agent.progress import ProgressSink
from pathlib import Path


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