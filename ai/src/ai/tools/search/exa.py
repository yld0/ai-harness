"""Exa (formerly Metaphor) search API."""

from __future__ import annotations

import os
from typing import Any, ClassVar

import httpx

from ai.tools._base import Tool, ToolResult, err_result, ok_result
from ai.tools.context import ToolContext
from ai.tools.search.common import with_http_retry


class ExaSearchTool(Tool):
    name: ClassVar[str] = "exa_search"
    description: ClassVar[str] = "Neural/keyword web search using Exa."
    file_component_risk: ClassVar[bool] = False

    @property
    def parameters_json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "num_results": {"type": "integer", "default": 8},
            },
            "required": ["query"],
        }

    async def _execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        key = os.getenv("EXA_API_KEY", "")
        if not key:
            return err_result("not_configured", "EXA_API_KEY is not set")
        q = str(args.get("query", ""))
        n = int(args.get("num_results", 8))
        if not q:
            return err_result("invalid_argument", "query is required")
        body = {
            "query": q,
            "numResults": n,
        }
        headers = {"x-api-key": key, "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await with_http_retry(
                lambda: client.post(
                    "https://api.exa.ai/search",
                    json=body,
                    headers=headers,
                )
            )
        r.raise_for_status()
        return ok_result(r.json())
