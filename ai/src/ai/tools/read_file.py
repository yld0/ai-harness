"""Read a memory or project file within a path allowlist (Phase 6)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, ClassVar

from ai.agent.prompt_builder import Channel
from ai.memory.para import ParaMemoryLayout
from ai.tools._base import Tool, ToolResult, err_result, ok_result
from ai.tools.context import ToolContext

_MAX_BYTES = 256 * 1024


def _normalise(p: str) -> Path:
    return Path(p).expanduser()


class ReadFileTool(Tool):
    name: ClassVar[str] = "read_file"
    description: ClassVar[str] = "Read a text file from the user's memory tree, global memory, or project skills. " "Path must stay within allowed roots."
    hidden_channels: ClassVar[frozenset[Channel]] = frozenset(("whatsapp", "discord"))  # type: ignore[arg-type]

    @property
    def parameters_json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path, or absolute path under an allowed root",
                },
            },
            "required": ["path"],
        }

    def _allowed_roots(self, ctx: ToolContext) -> list[Path]:
        layout = ParaMemoryLayout(ctx.memory_root)
        user_dir = layout.user_root(ctx.user_id)
        roots = [user_dir, layout.global_root(), ctx.project_root]
        extra = os.getenv("AI_READ_FILE_ROOTS", "")
        for part in extra.split(os.pathsep):
            part = part.strip()
            if part:
                roots.append(Path(part).expanduser().resolve())
        skills = os.getenv("AI_USER_SKILLS_DIR", "").strip()
        if skills:
            roots.append(Path(skills).expanduser().resolve())
        return [p.resolve() for p in roots]

    def _resolve(self, ctx: ToolContext, target: str) -> Path:
        t = _normalise(target)
        layout = ParaMemoryLayout(ctx.memory_root)
        if t.is_absolute():
            candidate = t.resolve()
        else:
            candidates = [
                layout.user_root(ctx.user_id) / t,
                ctx.project_root / t,
                layout.global_root() / t,
            ]
            candidate = None
            for c in candidates:
                if c.exists():
                    candidate = c.resolve()
                    break
            if candidate is None:
                candidate = (layout.user_root(ctx.user_id) / t).resolve()
        for root in self._allowed_roots(ctx):
            try:
                candidate.relative_to(root)
                return candidate
            except ValueError:
                continue
        raise ValueError("path not under allowlist")

    async def _execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        rel = str(args.get("path", ""))
        if not rel:
            return err_result("invalid_argument", "path is required")
        try:
            path = self._resolve(ctx, rel)
        except ValueError as exc:
            return err_result("path_forbidden", str(exc))
        if not path.is_file():
            return err_result("not_found", f"Not a file: {path}")
        size = path.stat().st_size
        if size > _MAX_BYTES:
            return err_result("too_large", f"File exceeds {_MAX_BYTES} bytes")
        text = path.read_text(encoding="utf-8", errors="replace")
        return ok_result({"path": str(path), "content": text})
