"""Slash command: /dream — trigger auto_dream hook once for the session."""

from __future__ import annotations

from typing import Any

from ai.commands.base import CommandHandler, CommandResult


class DreamCommand(CommandHandler):
    name = "dream"

    async def handle(self, args: list[str], *, context: dict[str, Any]) -> CommandResult:
        return CommandResult(
            text="Auto-dream hook queued for this session.",
            side_effects={"trigger_hook": "auto_dream"},
        )
