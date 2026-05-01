"""Financial Modeling Prep API helpers (read-only external data)."""

from __future__ import annotations

import os
from typing import Any, ClassVar

import httpx

from ai.tools.base import Tool, ToolResult, err_result, ok_result
from ai.tools.context import ToolContext
from ai.tools.search.common import with_http_retry

_FMP = "https://financialmodelingprep.com/api/v3"


class FmpGetQuote(Tool):
    name: ClassVar[str] = "fmp_get_quote"
    description: ClassVar[str] = "Get a current US equity quote from Financial Modeling Prep."
    file_component_risk: ClassVar[bool] = False

    @property
    def parameters_json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol, e.g. MSFT"},
            },
            "required": ["symbol"],
        }

    async def _execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        symbol = str(args.get("symbol", "")).upper().strip()
        if not symbol:
            return err_result("invalid_argument", "symbol is required")
        key = os.getenv("FMP_API_KEY", "")
        if not key:
            return err_result("not_configured", "FMP_API_KEY is not set")
        url = f"{_FMP}/quote/{symbol}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await with_http_retry(
                lambda: client.get(url, params={"apikey": key}),
            )
        if response.status_code != 200:
            return err_result("fmp_error", f"HTTP {response.status_code}: {response.text[:200]}")
        data = response.json()
        if isinstance(data, list) and data:
            return ok_result(data[0])
        if isinstance(data, dict) and "Error Message" in data:
            return err_result("fmp_error", str(data.get("Error Message")))
        return ok_result(data)
