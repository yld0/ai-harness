"""Search expert (stub; real integration deferred)."""

from __future__ import annotations

from typing import Any, ClassVar

from ai.tools._base import Tool, ToolResult, err_result
from ai.tools.context import ToolContext


class SearchExpertToolStub(Tool):
    name: ClassVar[str] = "search_expert"
    description: ClassVar[str] = "Search internal expert or curated source index (not configured in this build)."
    file_component_risk: ClassVar[bool] = False

    @property
    def parameters_json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        }

    async def _execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        return err_result("not_configured", "search_expert is not configured in Phase 6")
