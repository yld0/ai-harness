"""Perplexity chat completions (search)."""

from __future__ import annotations

import os
from typing import Any, ClassVar

import httpx

from ai.tools.base import Tool, ToolResult, err_result, ok_result
from ai.tools.context import ToolContext
from ai.tools.search.common import with_http_retry


class PerplexitySearchTool(Tool):
    name: ClassVar[str] = "perplexity_search"
    description: ClassVar[str] = "Query Perplexity's chat API for grounded answers."
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
        key = os.getenv("PERPLEXITY_API_KEY", "")
        if not key:
            return err_result("not_configured", "PERPLEXITY_API_KEY is not set")
        q = str(args.get("query", ""))
        if not q:
            return err_result("invalid_argument", "query is required")
        body = {
            "model": "sonar",
            "messages": [
                {"role": "user", "content": q},
            ],
        }
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await with_http_retry(
                lambda: client.post(
                    "https://api.perplexity.ai/chat/completions",
                    json=body,
                    headers=headers,
                )
            )
        r.raise_for_status()
        return ok_result(r.json())
