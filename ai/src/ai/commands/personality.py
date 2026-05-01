"""Slash command: /personality list | /personality <name>."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ai.commands.base import CommandHandler, CommandResult
from ai.agent.personalities.loader import PersonalityLoader, PersonalityNotFound


class PersonalityCommand(CommandHandler):
    name = "personality"
    aliases = ("persona",)

    async def handle(self, args: list[str], *, context: dict[str, Any]) -> CommandResult:
        repo_root: Path | None = context.get("repo_root")
        workspace_root: Path | None = context.get("workspace_root")
        loader = PersonalityLoader(workspace_root=workspace_root, repo_root=repo_root)

        if not args or args[0].lower() in ("list", "ls"):
            personalities = loader.list()
            if not personalities:
                return CommandResult(text="No personalities found.")
            lines = [f"- **{p.name}**: {p.description or '(no description)'}" for p in personalities]
            return CommandResult(text="Personalities:\n" + "\n".join(lines))

        target_name = args[0]
        try:
            p = loader.get(target_name)
        except PersonalityNotFound as exc:
            return CommandResult(
                text=f"Unknown personality: {exc}",
                dispatched=True,
                error="personality_not_found",
            )
        return CommandResult(
            text=f"Personality set to **{p.name}**.",
            side_effects={"personality": p.name},
        )
