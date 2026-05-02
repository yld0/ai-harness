"""Search PARA user memory; optional qmd when installed."""

from __future__ import annotations

from typing import Any, ClassVar

from ai.memory.para import ParaMemoryLayout
from ai.memory.search import MemorySearch
from ai.tools._base import Tool, ToolResult, ok_result
from ai.tools.context import ToolContext

_layout = ParaMemoryLayout()


class MemorySearchTool(Tool):
    name: ClassVar[str] = "memory_search"
    description: ClassVar[str] = "Search the user's local PARA memory (markdown/YAML) for relevant notes."
    file_component_risk: ClassVar[bool] = False

    @property
    def parameters_json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "use_qmd": {
                    "type": "boolean",
                    "description": "If true, try qmd when available",
                    "default": False,
                },
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        }

    async def _execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        q = str(args.get("query", ""))
        limit = int(args.get("limit", 10))
        use_qmd = bool(args.get("use_qmd", False))
        root = ctx.memory_root
        search = MemorySearch(ParaMemoryLayout(root))
        if use_qmd:
            results = search.qmd_query(ctx.user_id, q, limit=limit)
        else:
            results = search.local_search(ctx.user_id, q, limit=limit)
        rows = [{"path": r.path, "score": r.score, "snippet": r.snippet} for r in results]
        return ok_result({"results": rows})
