"""File-based personality discovery and loading.

Discovery roots (low priority → high; later roots shadow earlier ones):
  1. Repo ``personalities/`` (vendored defaults)  ← lowest
  2. ``~/.ai/personalities/``
  3. ``<workspace>/personalities/``               ← highest

File format: ``personalities/<name>.md`` with YAML front-matter::

    ---
    name: codereviewer
    description: Terse, risk-focused reviewer voice.
    effort_hint: medium
    ---

    You are reviewing code and finance theses with...

The front-matter body is appended at slot 12 of the prompt stack when the
personality is active.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


class PersonalityNotFound(Exception):
    pass


@dataclass(frozen=True)
class Personality:
    name: str
    description: str
    prompt: str
    effort_hint: Optional[str] = None


# --------------------------------------------------------------------------- #
# Internal parser                                                               #
# --------------------------------------------------------------------------- #


def _parse_personality_file(path: Path) -> Personality:
    """Parse YAML front-matter + body from a personality markdown file."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    front: dict = {}
    body = raw
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            try:
                front = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError as exc:
                logger.warning("YAML parse error in %s: %s", path, exc)
            body = parts[2].strip()
    name = str(front.get("name") or path.stem).strip().lower()
    description = str(front.get("description") or "").strip()
    effort_hint_raw = front.get("effort_hint")
    effort_hint = str(effort_hint_raw).strip() if effort_hint_raw else None
    return Personality(name=name, description=description, prompt=body, effort_hint=effort_hint)


# --------------------------------------------------------------------------- #
# Loader                                                                        #
# --------------------------------------------------------------------------- #


class PersonalityLoader:
    """Discover and load personality files from configured roots.

    Args:
        workspace_root: Optional workspace directory; its ``personalities/``
                        subdirectory has the highest priority.
        repo_root:      Repo / project root.  Defaults to the ``ai/`` project
                        directory (four parents up from this file).
    """

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        repo_root: Optional[Path] = None,
    ) -> None:
        self._workspace_root = workspace_root
        # ai/src/ai/agent/personalities/loader.py → parents[4] = ai/ project root
        self._repo_root: Path = repo_root or Path(__file__).resolve().parents[4]

    # ------------------------------------------------------------------ #
    # Private                                                               #
    # ------------------------------------------------------------------ #

    def _discovery_roots(self) -> list[Path]:
        """Return roots ordered from lowest to highest priority."""
        roots: list[Path] = [
            self._repo_root / "personalities",  # vendored defaults (lowest)
            Path.home() / ".ai" / "personalities",  # user home
        ]
        if self._workspace_root is not None:
            roots.append(self._workspace_root / "personalities")  # workspace (highest)
        return roots

    def _load_all(self) -> dict[str, Personality]:
        """Scan all roots low→high so higher-priority files shadow lower ones."""
        found: dict[str, Personality] = {}
        for root in self._discovery_roots():
            if not root.is_dir():
                continue
            for md_file in sorted(root.glob("*.md")):
                try:
                    p = _parse_personality_file(md_file)
                    found[p.name] = p
                except Exception as exc:  # noqa: BLE001
                    logger.warning("failed to parse personality file %s: %s", md_file, exc)
        return found

    # ------------------------------------------------------------------ #
    # Public API                                                            #
    # ------------------------------------------------------------------ #

    def list(self) -> list[Personality]:
        """Return all discovered personalities sorted by name."""
        return sorted(self._load_all().values(), key=lambda p: p.name)

    def get(self, name: str) -> Personality:
        """Return the named personality or raise ``PersonalityNotFound``."""
        all_p = self._load_all()
        key = name.strip().lower()
        match = all_p.get(key)
        if match is None:
            available = sorted(all_p)
            raise PersonalityNotFound(f"Personality {name!r} not found. Available: {available}")
        return match
