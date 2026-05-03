""" Skill directory discovery, shadowing, and index assembly. """

from __future__ import annotations

import os
from collections import OrderedDict
from pathlib import Path
from typing import Any

import yaml

from ai.skills.eligibility import is_eligible
from ai.skills.prompt import (
    build_skills_prompt,
    DEFAULT_MAX_PROMPT_CHARS,
    DEFAULT_READ_TOOL_NAME,
)
from ai.skills.safety import (
    MAX_SKILL_FILE_BYTES,
    resolve_realpath_safely,
    scan_injection_hits,
    should_reject_on_injection,
)
from ai.skills.types import SessionPermission, SkillIndexEntry, SkillsBuildResult

# OpenClaw hard limits
MAX_CANDIDATE_DIRS = 300
MAX_SKILLS_PER_RUN = 200


def _parse_front_matter_text(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            block = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1 :])
            if body and not body.startswith("\n"):
                body = "\n" + body
            try:
                fm = yaml.safe_load(block) or {}
            except yaml.YAMLError:
                return {}, text
            if not isinstance(fm, dict):
                return {}, text
            return fm, body
    return {}, text


def _parse_front_matter(path: Path) -> tuple[dict[str, Any], str]:
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except OSError:
        return {}, ""
    return _parse_front_matter_text(text)


def _fallback_name_from_dir(skill_dir: Path) -> str:
    return skill_dir.name.strip()


def _discover_in_root(
    root: Path,
    source_tag: str,
    merged: OrderedDict[str, SkillIndexEntry],
) -> None:
    if not root.is_dir():
        return
    seen_dirs = 0
    for skill_dir in sorted(root.iterdir(), key=lambda p: p.name.casefold()):
        if not skill_dir.is_dir():
            continue
        if seen_dirs >= MAX_CANDIDATE_DIRS:
            break
        seen_dirs += 1
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            st = skill_md.stat()
        except OSError:
            continue
        if st.st_size > MAX_SKILL_FILE_BYTES:
            continue
        try:
            fm, body = _parse_front_matter(skill_md)
        except OSError:
            continue
        name_raw = (fm.get("name") or "").strip() if isinstance(fm, dict) else ""
        if not name_raw and isinstance(fm, dict) and "name" in fm and fm.get("name") is None:
            name_raw = ""
        name = name_raw or _fallback_name_from_dir(skill_dir)
        desc = ""
        if isinstance(fm, dict):
            desc = str(fm.get("description") or "").strip()
        if not name or not desc:
            continue
        if should_reject_on_injection(scan_injection_hits(body[: min(len(body), 200_000)])):
            continue
        merged[name] = SkillIndexEntry(
            name=name,
            description=desc,
            skill_md_path=skill_md.resolve(),
            source=source_tag,
            frontmatter=dict(fm) if isinstance(fm, dict) else {},
        )


def _user_skills_path() -> Path:
    custom = os.environ.get("AI_USER_SKILLS_DIR")
    if custom:
        return Path(custom).expanduser().resolve()
    return (Path.home() / ".ai" / "skills").resolve()


def skill_discovery_roots(*, repo_root: Path) -> list[tuple[Path, str]]:
    """
    Return roots from lowest to highest priority (last wins for same ``name``).

    Order: ``references-skills/`` < user ``~/.ai/skills/`` (or :envvar:`AI_USER_SKILLS_DIR`) <
    repo ``skills/`` (workspace).
    """
    rr = resolve_realpath_safely(repo_root)
    return [
        (rr / "references-skills", "references-skills"),
        (_user_skills_path(), "user"),
        (rr / "skills", "workspace"),
    ]


def build_skill_index(
    repo_root: Path,
    *,
    session_permission: SessionPermission = "ReadWrite",
    eligibility_config: dict[str, Any] | None = None,
) -> list[SkillIndexEntry]:
    """
    Walk discovery roots, merge with shadowing, filter eligibility + permission, sort.
    """
    roots = skill_discovery_roots(repo_root=repo_root)
    merged: OrderedDict[str, SkillIndexEntry] = OrderedDict()
    for rpath, tag in roots:
        _discover_in_root(rpath, tag, merged)
    if len(merged) > MAX_SKILLS_PER_RUN:
        keys = sorted(merged.keys(), key=lambda s: s.casefold())
        merged = OrderedDict((k, merged[k]) for k in keys[:MAX_SKILLS_PER_RUN])
    out: list[SkillIndexEntry] = []
    for entry in merged.values():
        fm = entry.frontmatter
        if not is_eligible(fm, permission=session_permission, config=eligibility_config or {}):
            continue
        out.append(entry)
    return sorted(out, key=lambda e: (e.name.casefold(), e.skill_md_path.as_posix()))


def build_skills_system_block(
    repo_root: Path,
    *,
    read_tool_name: str = DEFAULT_READ_TOOL_NAME,
    max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS,
    session_permission: SessionPermission = "ReadWrite",
    eligibility_config: dict[str, Any] | None = None,
) -> SkillsBuildResult:
    entries = build_skill_index(
        repo_root,
        session_permission=session_permission,
        eligibility_config=eligibility_config,
    )
    return build_skills_prompt(list(entries), read_tool_name=read_tool_name, max_chars=max_prompt_chars)
