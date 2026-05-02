"""Agent-callable heartbeat / continuity ping (long-poll watcher contract)."""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from ai.tools._base import Tool, ToolResult, ok_result
from ai.tools.context import ToolContext

_DEFAULT_WAIT_S = 0.0


class HeartbeatTool(Tool):
    name: ClassVar[str] = "heartbeat"
    description: ClassVar[str] = (
        "Record a liveness/continuity check during a long run. The agent can call this mid-conversation; "
        "it does not replace server automations (heartbeat-extract route)."
    )
    file_component_risk: ClassVar[bool] = False

    @property
    def parameters_json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Short description for logs/UI",
                },
                "wait_s": {
                    "type": "number",
                    "default": 0.0,
                    "description": "Optional busy-wait to simulate a long-poll (tests only)",
                },
            },
        }

    async def _execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        label = str(args.get("label", "ok"))
        wait_s = float(args.get("wait_s", _DEFAULT_WAIT_S) or 0.0)
        if wait_s > 0:
            await asyncio.sleep(min(wait_s, 5.0))
        return ok_result(
            {
                "status": "ok",
                "label": label,
                "user_id": ctx.user_id,
            }
        )
