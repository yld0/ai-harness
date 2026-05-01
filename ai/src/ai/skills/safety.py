"""Path containment, size limits, and prompt-injection heuristics (skills_guard parity, subset)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

# OpenClaw / Hermes default
MAX_SKILL_FILE_BYTES = 256 * 1024

# High-signal injection patterns (subset of references/hermes-agent-main/tools/skills_guard.py)
_INJECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"ignore\s+(?:\w+\s+)*(previous|all|above|prior)\s+instructions",
            re.IGNORECASE,
        ),
        "prompt_injection_ignore",
    ),
    (re.compile(r"system\s+prompt\s+override", re.IGNORECASE), "sys_prompt_override"),
    (
        re.compile(r"disregard\s+.*(instructions|rules|guidelines)", re.IGNORECASE),
        "disregard_rules",
    ),
    (
        re.compile(r"output\s+.*(system|initial)\s+prompt", re.IGNORECASE),
        "leak_system_prompt",
    ),
]


def resolve_realpath_safely(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


def is_under_any_root(path: Path, roots: Iterable[Path]) -> bool:
    """True if *path* (after resolve) is equal to or under one of *roots* (after resolve)."""
    candidate = resolve_realpath_safely(path)
    for root in roots:
        base = resolve_realpath_safely(root)
        if base == candidate:
            return True
        try:
            candidate.relative_to(base)
            return True
        except ValueError:
            continue
    return False


def scan_injection_hits(text: str) -> list[str]:
    """Return pattern ids for suspected prompt-injection content."""
    hits: list[str] = []
    for pattern, pid in _INJECTION_PATTERNS:
        if pattern.search(text):
            hits.append(pid)
    return hits


def should_reject_on_injection(hits: list[str]) -> bool:
    """Reject SKILL.md body when any critical hit is present (strict gate for this phase)."""
    return bool(hits)
