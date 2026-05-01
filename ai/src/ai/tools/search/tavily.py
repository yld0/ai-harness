"""Tavily web search API."""

from __future__ import annotations

import os
from typing import Any, ClassVar

import httpx

from ai.tools.base import Tool, ToolResult, err_result, ok_result
from ai.tools.context import ToolContext
from ai.tools.search.common import with_http_retry


class TavilySearchTool(Tool):
    name: ClassVar[str] = "tavily_search"
    description: ClassVar[str] = "Search the web via Tavily."
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
        key = os.getenv("TAVILY_API_KEY", "")
        if not key:
            return err_result("not_configured", "TAVILY_API_KEY is not set")
        q = str(args.get("query", ""))
        if not q:
            return err_result("invalid_argument", "query is required")
        body = {
            "api_key": key,
            "query": q,
            "include_answer": True,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await with_http_retry(
                lambda: client.post("https://api.tavily.com/search", json=body),
            )
        r.raise_for_status()
        return ok_result(r.json())
