"""PARA memory root resolution and path guards."""

import os
import re
from pathlib import Path
from typing import Literal

MemoryEntityKind = Literal["tickers", "sectors", "spaces", "watchlists", "people", "macros"]

SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class MemoryPathError(ValueError):
    pass


class ParaMemoryLayout:
    def __init__(self, memory_root: Path | str | None = None) -> None:
        root = memory_root or os.getenv("MEMORY_ROOT") or "./memory"
        self.memory_root = Path(root).expanduser().resolve()

    def user_root(self, user_id: str) -> Path:
        return self._ensure_under_root(self.memory_root / "users" / self._safe_segment(user_id))

    def global_root(self) -> Path:
        return self._ensure_under_root(self.memory_root / "global")

    def ensure_user_layout(self, user_id: str) -> Path:
        root = self.user_root(user_id)
        for path in (
            root / "life" / "tickers",
            root / "life" / "sectors",
            root / "life" / "spaces",
            root / "life" / "watchlists",
            root / "life" / "people",
            root / "life" / "macros",
            root / "goals",
            root / "memory",
        ):
            path.mkdir(parents=True, exist_ok=True)
        for file_name in ("USER.md", "MEMORY.md"):
            path = root / file_name
            if not path.exists():
                path.write_text("", encoding="utf-8")
        return root

    def entity_dir(self, user_id: str, kind: MemoryEntityKind, entity_id: str) -> Path:
        root = self.ensure_user_layout(user_id)
        path = root / "life" / kind / self._safe_segment(entity_id)
        return self._ensure_under_user_root(user_id, path)

    def daily_note_path(self, user_id: str, day: str) -> Path:
        path = self.ensure_user_layout(user_id) / "memory" / f"{self._safe_segment(day)}.md"
        return self._ensure_under_user_root(user_id, path)

    def guarded_user_path(self, user_id: str, *parts: str) -> Path:
        path = self.user_root(user_id).joinpath(*parts).resolve()
        return self._ensure_under_user_root(user_id, path)

    def _ensure_under_root(self, path: Path) -> Path:
        resolved = path.resolve()
        if not self._is_relative_to(resolved, self.memory_root):
            raise MemoryPathError(f"path escapes MEMORY_ROOT: {path}")
        return resolved

    def _ensure_under_user_root(self, user_id: str, path: Path) -> Path:
        resolved = path.resolve()
        user_root = self.user_root(user_id)
        if not self._is_relative_to(resolved, user_root):
            raise MemoryPathError(f"path escapes user memory root: {path}")
        return resolved

    @staticmethod
    def _safe_segment(value: str) -> str:
        if value in {"", ".", ".."} or "/" in value or "\\" in value:
            raise MemoryPathError(f"unsafe memory path segment: {value!r}")
        if not SAFE_SEGMENT_RE.match(value):
            raise MemoryPathError(f"unsafe memory path segment: {value!r}")
        return value

    @staticmethod
    def _is_relative_to(path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False
