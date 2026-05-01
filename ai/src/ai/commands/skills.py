"""Slash helpers for /skill (list, view) and SkillCommand handler."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ai.commands.base import CommandHandler, CommandResult
from ai.skills.loader import SkillLoadError, read_skill_file
from ai.skills.registry import build_skill_index, skill_discovery_roots
from ai.skills.safety import resolve_realpath_safely


def allowed_roots(*, repo_root: Path) -> list[Path]:
    return [resolve_realpath_safely(p) for p, _ in skill_discovery_roots(repo_root=resolve_realpath_safely(repo_root))]


def skill_list_text(*, repo_root: Path) -> str:
    entries = build_skill_index(resolve_realpath_safely(repo_root))
    if not entries:
        return "No skills discovered under references-skills/, ~/.ai/skills/, or <repo>/skills/."
    lines = [f"- {e.name} — {e.description.splitlines()[0][:120]}" for e in entries]
    return "Skills:\n" + "\n".join(lines)


def skill_view_by_name(
    name: str,
    *,
    repo_root: Path,
) -> str:
    entries = build_skill_index(resolve_realpath_safely(repo_root))
    match = next((e for e in entries if e.name.casefold() == name.strip().casefold()), None)
    if match is None:
        return f"Unknown skill: {name!r}. Use /skill list."
    try:
        body = read_skill_file(
            match.skill_md_path,
            allowed_roots=allowed_roots(repo_root=resolve_realpath_safely(repo_root)),
        )
    except SkillLoadError as exc:
        return f"Failed to read skill: {exc.message}"
    return f"# {match.name}\n{body}"


class SkillCommand(CommandHandler):
    """Handler for /skill list | /skill view <name>."""

    name = "skill"
    aliases = ("skills",)

    async def handle(self, args: list[str], *, context: dict[str, Any]) -> CommandResult:
        repo_root: Path = context.get("repo_root") or Path(".")
        if not args or args[0].lower() in ("list", "ls"):
            text = skill_list_text(repo_root=repo_root)
        elif args[0].lower() == "view" and len(args) >= 2:
            text = skill_view_by_name(" ".join(args[1:]), repo_root=repo_root)
        else:
            text = "Usage: /skill list | /skill view <name>"
        return CommandResult(text=text)
