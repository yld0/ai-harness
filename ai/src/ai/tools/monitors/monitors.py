"""Agent-callable tool for managing the user's monitoring checklist."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar

from ai.clients.automations import AutomationsClient, find_automation_by_route
from ai.tools._base import Tool, ToolResult, err_result, ok_result
from ai.tools.types import ToolContext
from ai.tools.permissions import PermissionMode

logger = logging.getLogger(__name__)

MONITORS_ROUTE = "monitors-check"
MONITORS_FILE = "MONITORS.md"
MONITORS_DIR = "monitors"
DEFAULT_INTERVAL_MINUTES = 10

MONITORS_TOOL_DESCRIPTION = """\
Manage the user's periodic monitoring checklist (MONITORS.md).
A scheduled automation reads this checklist to decide what to check.
When items are added the automation is automatically enabled.

## When to Use

- User asks to add, remove, or change what is being monitored
- User asks "what am I monitoring?" or similar
- User says things like "watch NVDA below $120", "stop checking TSLA", "monitor Fed minutes for rate cuts"

## Actions

- view: Show the current monitoring checklist
- update: Replace the checklist with new content (provide full markdown)

## Update Tips

- Always view first before update to see current content
- Preserve existing items the user did not ask to change
- Use structured markdown format with ## headings per item
"""


class MonitorsTool(Tool):
    """View or update the monitoring checklist that controls periodic checks."""

    name: ClassVar[str] = "monitors"
    description: ClassVar[str] = MONITORS_TOOL_DESCRIPTION.strip()
    required_permission: ClassVar[PermissionMode] = PermissionMode.WorkspaceWrite
    file_component_risk: ClassVar[bool] = False

    @property
    def parameters_json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["view", "update"],
                    "description": "Whether to view or update the monitoring checklist.",
                },
                "content": {
                    "type": "string",
                    "description": "New MONITORS.md content (required for update).",
                },
            },
            "required": ["action"],
        }

    async def _execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "view")
        monitors_path = self._monitors_path(ctx)

        if action == "view":
            return self._handle_view(monitors_path)

        if action == "update":
            content = args.get("content")
            if not content:
                return err_result("missing_content", "content is required for the update action.")
            return await self._handle_update(ctx, monitors_path, content)

        return err_result("unknown_action", f"Unknown action {action!r}. Use 'view' or 'update'.")

    def _monitors_path(self, ctx: ToolContext) -> Path:
        """Resolve the per-user MONITORS.md path within PARA."""
        return ctx.memory_root / "users" / ctx.user_id / "life" / MONITORS_DIR / MONITORS_FILE

    def _handle_view(self, monitors_path: Path) -> ToolResult:
        """Return current checklist contents or a helpful default message."""
        if not monitors_path.is_file():
            return ok_result(
                {
                    "status": "empty",
                    "message": ("No monitoring checklist configured yet. Use the update action to add items you want monitored on a schedule."),
                }
            )
        content = monitors_path.read_text("utf-8")
        return ok_result({"status": "ok", "content": content})

    async def _handle_update(self, ctx: ToolContext, monitors_path: Path, content: str) -> ToolResult:
        """Write new checklist content and sync the automation schedule."""
        monitors_path.parent.mkdir(parents=True, exist_ok=True)
        monitors_path.write_text(content, "utf-8")

        item_count = sum(1 for line in content.splitlines() if line.startswith("## "))
        has_items = item_count > 0

        scheduling_note = ""
        if ctx.bearer_token:
            scheduling_note = await self._sync_automation(ctx, has_items)

        summary = f"Updated monitoring checklist ({item_count} item{'s' if item_count != 1 else ''})." if has_items else "Cleared monitoring checklist."
        if scheduling_note:
            summary = f"{summary} {scheduling_note}"

        return ok_result({"status": "ok", "items": item_count, "message": summary})

    async def _sync_automation(self, ctx: ToolContext, has_items: bool) -> str:
        """Create, resume, or pause the monitors automation as needed."""
        try:
            existing = await find_automation_by_route(ctx.bearer_token, MONITORS_ROUTE)  # type: ignore[arg-type]
            client = AutomationsClient()

            if has_items:
                if existing is None:
                    await client.create_automation(
                        bearer_token=ctx.bearer_token,  # type: ignore[arg-type]
                        name="Monitors Check",
                        route=MONITORS_ROUTE,
                        description="Periodic check of user monitoring checklist",
                        schedule={"type": "INTERVAL", "intervalMinutes": DEFAULT_INTERVAL_MINUTES},
                        target={"type": "ROUTE", "ref": MONITORS_ROUTE},
                    )
                    return f"Automation created (every {DEFAULT_INTERVAL_MINUTES}min)."
                if existing.get("status") == "PAUSED":
                    await client.resume_automation(
                        bearer_token=ctx.bearer_token,  # type: ignore[arg-type]
                        automation_id=existing["id"],
                    )
                    return "Automation resumed."
                return ""
            else:
                if existing is not None and existing.get("status") == "ACTIVE":
                    await client.pause_automation(
                        bearer_token=ctx.bearer_token,  # type: ignore[arg-type]
                        automation_id=existing["id"],
                    )
                    return "Automation paused (no items)."
                return ""
        except Exception as exc:
            logger.warning("monitors: failed to sync automation: %s", exc)
            return f"(scheduling sync failed: {exc})"
