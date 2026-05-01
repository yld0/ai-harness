"""Slash command: /compact — trigger compact hook on session buffer."""

from __future__ import annotations

from typing import Any

from ai.commands.base import CommandHandler, CommandResult


class CompactCommand(CommandHandler):
    name = "compact"

    async def handle(self, args: list[str], *, context: dict[str, Any]) -> CommandResult:
        return CommandResult(
            text="Compact hook queued for this session.",
            side_effects={"trigger_hook": "compact"},
        )
