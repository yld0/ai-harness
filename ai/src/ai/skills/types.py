"""Shared datatypes for skills discovery and prompting."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

SessionPermission = Literal["ReadOnly", "ReadWrite"]


@dataclass(frozen=True, order=True)
class SkillIndexEntry:
    """One skill after discovery, eligibility, and permission gating."""

    name: str
    description: str
    skill_md_path: Path
    source: str
    frontmatter: dict[str, Any] = field(compare=False, hash=False, repr=False)


@dataclass(frozen=True)
class SkillsBuildResult:
    """Prompt string plus bookkeeping for tests and slash commands."""

    prompt_text: str
    entries: tuple[SkillIndexEntry, ...]
    compact: bool
    truncated: bool
    approx_tokens: int
