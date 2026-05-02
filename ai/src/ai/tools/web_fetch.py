"""HTTP(S) fetch with size and time limits."""

from __future__ import annotations

import os
from typing import Any, ClassVar

import httpx

from ai.tools._base import Tool, ToolResult, err_result, ok_result
from ai.tools.context import ToolContext
from ai.tools.search.common import with_http_retry

_DEFAULT_MAX = 1_000_000
_DEFAULT_TIMEOUT = 20.0


class WebFetchTool(Tool):
    name: ClassVar[str] = "web_fetch"
    description: ClassVar[str] = "GET a public HTTP/HTTPS URL and return the body (with size and timeout limits)."
    file_component_risk: ClassVar[bool] = False

    @property
    def parameters_json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "http(s) URL"},
            },
            "required": ["url"],
        }

    async def _execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        url = str(args.get("url", "")).strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            return err_result("invalid_url", "Only http and https URLs are allowed")
        max_bytes = int(os.getenv("AI_WEB_FETCH_MAX_BYTES", str(_DEFAULT_MAX)))
        timeout = float(os.getenv("AI_WEB_FETCH_TIMEOUT_S", str(_DEFAULT_TIMEOUT)))
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await with_http_retry(
                lambda: client.get(
                    url,
                    follow_redirects=True,
                ),
            )
        head = {k: v for k, v in response.headers.items() if k.lower() in ("content-type", "content-length")}
        raw = response.content
        if len(raw) > max_bytes:
            return err_result("too_large", f"Response exceeds {max_bytes} bytes")
        text = raw.decode("utf-8", errors="replace")
        return ok_result(
            {
                "status": response.status_code,
                "headers": head,
                "text": text,
            }
        )
