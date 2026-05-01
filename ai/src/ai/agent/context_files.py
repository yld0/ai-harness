"""Load project context files for the system prompt.

Discovery strategy (Phase 12 extended)
--------------------------------------
1. Search ``root`` for the first matching AGENTS.md / .cursorrules / CLAUDE.md
   file (same as Phase 2).
2. If a ``workspace_root`` is provided and differs from ``root``, also search
   upward from ``workspace_root`` (up to ``MAX_ANCESTOR_LEVELS`` parent
   directories) to pick up the nearest project-level context file.
3. Include ``root / "SOUL.md"`` in the context files block when it exists *and*
   its content is non-default (i.e. a custom SOUL.md is present).  The same
   text already populates slot 01_identity, but surfacing it in slot 09 lets
   the model refer to it as a named document rather than an invisible constraint.
4. Scan ``root / ".cursor" / "rules"`` for ``*.mdc`` files as before.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ai.agent.personality import DEFAULT_AGENT_IDENTITY

CONTEXT_FILE_NAMES = (
    "AGENTS.md",
    "agents.md",
    "CLAUDE.md",
    "claude.md",
    ".cursorrules",
)
MAX_CONTEXT_FILE_CHARS = 20_000
MAX_ANCESTOR_LEVELS = 5


@dataclass(frozen=True)
class ContextFile:
    path: str
    content: str


@dataclass(frozen=True)
class ContextFilesSnapshot:
    identity: str
    files: list[ContextFile]


class ContextFilesLoader:
    def __init__(
        self,
        root: "Path | str | None" = None,
        workspace_root: Optional[Path] = None,
    ) -> None:
        self.root = Path(root).resolve() if root is not None else Path.cwd().resolve()
        self.workspace_root = workspace_root.resolve() if workspace_root is not None else None

    def load(self) -> ContextFilesSnapshot:
        identity = self._load_identity()
        files: list[ContextFile] = []
        seen_paths: set[Path] = set()

        # 1. Primary root context file (AGENTS.md, .cursorrules, …)
        primary = self._find_in_dir(self.root)
        if primary is not None and primary not in seen_paths:
            files.append(ContextFile(path=str(primary), content=self._read_truncated(primary)))
            seen_paths.add(primary)

        # 2. Workspace upward search — finds the nearest project context file
        #    in ancestors when workspace_root differs from root.
        if self.workspace_root is not None and self.workspace_root != self.root:
            ws_file = self._find_upward(self.workspace_root)
            if ws_file is not None and ws_file not in seen_paths:
                files.append(ContextFile(path=str(ws_file), content=self._read_truncated(ws_file)))
                seen_paths.add(ws_file)

        # 3. SOUL.md — include as named document when a custom one is present.
        soul_path = self.root / "SOUL.md"
        if soul_path.is_file() and soul_path not in seen_paths:
            soul_content = self._read_truncated(soul_path).strip()
            if soul_content and soul_content != DEFAULT_AGENT_IDENTITY:
                files.append(ContextFile(path=str(soul_path), content=soul_content))
                seen_paths.add(soul_path)

        # 4. Cursor rules directory
        cursor_rules = self.root / ".cursor" / "rules"
        if cursor_rules.is_dir():
            for path in sorted(cursor_rules.glob("*.mdc")):
                if path not in seen_paths:
                    files.append(ContextFile(path=str(path), content=self._read_truncated(path)))
                    seen_paths.add(path)

        return ContextFilesSnapshot(identity=identity, files=files)

    # ------------------------------------------------------------------ #
    # Private helpers                                                       #
    # ------------------------------------------------------------------ #

    def _load_identity(self) -> str:
        for path in (self.root / "SOUL.md", Path.home() / ".ai" / "SOUL.md"):
            if path.is_file():
                content = self._read_truncated(path).strip()
                if content:
                    return content
        return DEFAULT_AGENT_IDENTITY

    @staticmethod
    def _find_in_dir(directory: Path) -> Optional[Path]:
        """Return the first matching context file name found in *directory*."""
        for name in CONTEXT_FILE_NAMES:
            path = directory / name
            if path.is_file():
                return path
        return None

    def _find_upward(self, start: Path) -> Optional[Path]:
        """Walk upward from *start* up to MAX_ANCESTOR_LEVELS looking for a
        context file.  Stops early if the directory reaches the filesystem root
        or the loader's own root (which is already searched).
        """
        current = start.resolve()
        for _ in range(MAX_ANCESTOR_LEVELS):
            found = self._find_in_dir(current)
            if found is not None:
                return found
            parent = current.parent
            if parent == current or current == self.root:
                break
            current = parent
        return None

    @staticmethod
    def _read_truncated(path: Path) -> str:
        content = path.read_text(encoding="utf-8", errors="replace").strip()
        if len(content) > MAX_CONTEXT_FILE_CHARS:
            return content[:MAX_CONTEXT_FILE_CHARS].rstrip() + "\n[truncated]"
        return content
