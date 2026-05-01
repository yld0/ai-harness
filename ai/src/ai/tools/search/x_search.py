"""X / Twitter search (provider-specific env key)."""

from __future__ import annotations

import os
from typing import Any, ClassVar

import httpx

from ai.tools.base import Tool, ToolResult, err_result, ok_result
from ai.tools.context import ToolContext
from ai.tools.search.common import with_http_retry

# X API v2 search recent tweets — URL may be overridden
_DEFAULT_URL = "https://api.x.com/2/tweets/search/recent"


class XSearchTool(Tool):
    name: ClassVar[str] = "x_search"
    description: ClassVar[str] = "Search recent posts on X; requires X bearer token."
    file_component_risk: ClassVar[bool] = False

    @property
    def parameters_json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (X API syntax)",
                },
            },
            "required": ["query"],
        }

    async def _execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        token = os.getenv("X_BEARER_TOKEN", "") or os.getenv("TWITTER_BEARER_TOKEN", "")
        if not token:
            return err_result("not_configured", "X_BEARER_TOKEN is not set")
        q = str(args.get("query", ""))
        if not q:
            return err_result("invalid_argument", "query is required")
        base = os.getenv("X_API_SEARCH_URL", _DEFAULT_URL)
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await with_http_retry(
                lambda: client.get(
                    base,
                    params={"query": q, "max_results": 10},
                    headers=headers,
                )
            )
        r.raise_for_status()
        return ok_result(r.json())
