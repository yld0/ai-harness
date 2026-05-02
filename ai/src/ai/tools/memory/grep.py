""" Ripgrep-like text search over memory trees (and optional project paths). """

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, ClassVar

from ai.memory.para import ParaMemoryLayout
from ai.tools._base import Tool, ToolResult, err_result, ok_result
from ai.tools.types import ToolContext

_MAX_HITS = 200


class GrepTool(Tool):
    name: ClassVar[str] = "grep"
    description: ClassVar[str] = "Search user PARA files for a pattern. Uses ripgrep (rg) when available, else Python line scan."
    file_component_risk: ClassVar[bool] = False

    @property
    def parameters_json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex or literal pattern",
                },
                "fixed": {
                    "type": "boolean",
                    "default": True,
                    "description": "If true, treat pattern as fixed string; else regex",
                },
            },
            "required": ["pattern"],
        }

    def _py_scan(self, root: Path, pat: re.Pattern[str]) -> list[dict[str, str]]:
        hits: list[dict[str, str]] = []
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {
                ".md",
                ".yaml",
                ".yml",
                ".txt",
                ".mdx",
            }:
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines, start=1):
                if pat.search(line) and len(hits) < _MAX_HITS:
                    rel = str(path.relative_to(root))
                    hits.append({"path": rel, "line": str(i), "text": line[:500]})
        return hits

    async def _execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        pattern = str(args.get("pattern", ""))
        if not pattern:
            return err_result("invalid_argument", "pattern is required")
        fixed = bool(args.get("fixed", True))
        layout = ParaMemoryLayout(ctx.memory_root)
        root = layout.user_root(ctx.user_id)
        if shutil.which("rg") and os.getenv("AI_GREP_PREFER_RIPGREP", "1") != "0":
            args_rg = [
                "rg",
                "--json",
                "--no-heading",
                "-i",
            ]
            if fixed:
                args_rg.extend(["-F", pattern, str(root)])
            else:
                args_rg.extend([pattern, str(root)])
            try:
                completed = subprocess.run(
                    args_rg,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except subprocess.TimeoutExpired:
                return err_result("timeout", "ripgrep timed out")
            lines_out = [line for line in completed.stdout.splitlines() if line.strip()][:_MAX_HITS]
            return ok_result(
                {
                    "mode": "ripgrep",
                    "lines": lines_out,
                    "returncode": completed.returncode,
                }
            )
        pat = re.compile(re.escape(pattern) if fixed else pattern, re.IGNORECASE)
        return ok_result(
            {
                "mode": "python",
                "matches": self._py_scan(root, pat),
            }
        )
