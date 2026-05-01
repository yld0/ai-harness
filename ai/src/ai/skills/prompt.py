"""Token-budgeted `<available_skills>` XML and mandatory instruction block."""

from __future__ import annotations

import os
import textwrap

from ai.config import agent_config
from ai.skills.types import SkillIndexEntry, SkillsBuildResult

DEFAULT_MAX_PROMPT_CHARS = agent_config.AI_SKILLS_INDEX_MAX_CHARS
DEFAULT_READ_TOOL_NAME = agent_config.AI_READ_TOOL_NAME


def estimate_tokens(s: str) -> int:
    return max(1, len(s) // 4)


def _compact_path_display(path: str) -> str:
    home = os.path.expanduser("~")
    if path.startswith(home + os.sep) or path == home:
        return path.replace(home, "~", 1)
    return path


def _format_entry_xml(entry: SkillIndexEntry, *, compact: bool) -> str:
    loc = _compact_path_display(str(entry.skill_md_path))
    if compact:
        desc = textwrap.shorten(entry.description.replace("\n", " "), width=200, placeholder="…")
    else:
        desc = entry.description.strip()
    return (
        "  <skill>\n"
        f"    <name>{_xml_escape(entry.name)}</name>\n"
        f"    <description>{_xml_escape(desc)}</description>\n"
        f"    <location>{_xml_escape(loc)}</location>\n"
        "  </skill>"
    )


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def mandatory_block(read_tool_name: str) -> str:
    return "\n".join(
        [
            "## Skills (mandatory)",
            "Before replying: scan <available_skills> <description> entries.",
            f"- If exactly one skill clearly applies: read its SKILL.md at <location> with `{read_tool_name}`, then follow it.",
            "- If multiple could apply: choose the most specific one, then read/follow it.",
            "- If none clearly apply: do not read any SKILL.md.",
            "Constraints: never read more than one skill up front; only read after selecting.",
        ]
    )


def _available_skills_block(lines: list[str], *, has_skills: bool) -> str:
    inner = "\n".join(lines) if lines else "  [none discovered]"
    return f"<available_skills>\n{inner}\n</available_skills>" if has_skills else f"<available_skills>\n{inner}\n</available_skills>"


def build_skills_prompt(
    entries: list[SkillIndexEntry],
    *,
    read_tool_name: str = DEFAULT_READ_TOOL_NAME,
    max_chars: int = DEFAULT_MAX_PROMPT_CHARS,
) -> SkillsBuildResult:
    sorted_entries = sorted(entries, key=lambda e: (e.name.casefold(), e.skill_md_path.as_posix()))
    instruction = mandatory_block(read_tool_name)
    skill_lines = [_format_entry_xml(e, compact=False) for e in sorted_entries]
    full_body = "The following skills provide specialized instructions for specific tasks."
    available = _available_skills_block(skill_lines, has_skills=bool(sorted_entries))
    full = "\n\n".join(
        [
            instruction,
            full_body,
            "When a skill is selected, use the read tool to load the file at <location> before following it.",
            available,
        ]
    )
    if len(full) <= max_chars:
        return SkillsBuildResult(
            prompt_text=full,
            entries=tuple(sorted_entries),
            compact=False,
            truncated=False,
            approx_tokens=estimate_tokens(full),
        )

    compact_lines = [_format_entry_xml(e, compact=True) for e in sorted_entries]
    available_c = _available_skills_block(compact_lines, has_skills=bool(sorted_entries))
    compact = "\n\n".join(
        [
            instruction,
            "Skills index (compact: name, short description, path only).",
            "When a skill is selected, use the read tool to load the file at <location> before following it.",
            available_c,
        ]
    )
    if len(compact) <= max_chars:
        return SkillsBuildResult(
            prompt_text=compact,
            entries=tuple(sorted_entries),
            compact=True,
            truncated=False,
            approx_tokens=estimate_tokens(compact),
        )

    # Binary-search drop skills in compact form until it fits
    lo, hi = 0, len(sorted_entries)
    best = 0
    while lo < hi:
        mid = (lo + hi + 1) // 2
        subset = sorted_entries[:mid]
        lines = [_format_entry_xml(e, compact=True) for e in subset]
        block = _available_skills_block(lines, has_skills=bool(subset))
        candidate = "\n\n".join(
            [
                instruction,
                "Skills index (compact; truncated to token budget).",
                "When a skill is selected, use the read tool to load the file at <location> before following it.",
                block,
            ]
        )
        if len(candidate) <= max_chars:
            best = mid
            lo = mid
        else:
            hi = mid - 1

    subset = sorted_entries[:best]
    lines = [_format_entry_xml(e, compact=True) for e in subset]
    final = "\n\n".join(
        [
            instruction,
            "Skills index (compact; truncated to token budget).",
            "When a skill is selected, use the read tool to load the file at <location> before following it.",
            _available_skills_block(lines, has_skills=bool(subset)),
        ]
    )
    return SkillsBuildResult(
        prompt_text=final,
        entries=tuple(subset),
        compact=True,
        truncated=best < len(sorted_entries),
        approx_tokens=estimate_tokens(final),
    )
