"""Route handler: actions-recent-earnings.

Summarises recent earnings releases for tickers in the user's watchlists/memory.
Input keys (all optional):
  - ``tickers``: list[str] — specific tickers to cover (defaults to watchlist).
  - ``days_back``: int — how far back to look (default 7).
  - ``system_hint``: str — extra system context.
"""

from __future__ import annotations

import logging

from ai.routes.context import RouteContext, RouteResult

logger = logging.getLogger(__name__)

_EARNINGS_PROMPT_TEMPLATE = """\
You are a financial research assistant.

Review earnings releases from the past {days_back} days{ticker_clause}.
Use the financial memory context available in your system prompt.

For each earnings event, provide:
- Ticker and company name
- EPS: actual vs estimate (beat/miss/in-line)
- Revenue: actual vs estimate
- Key guidance change (if any)
- One-sentence market reaction

Group by date (most recent first).
If no earnings data is available, say so.
Limit to {max_items} companies.
"""

_DEFAULT_MAX_ITEMS = 10


async def run(ctx: RouteContext) -> RouteResult:
    tickers: list[str] = ctx.input.get("tickers", [])
    days_back: int = int(ctx.input.get("days_back", 7))
    max_items: int = int(ctx.input.get("max_items", _DEFAULT_MAX_ITEMS))
    prompt_extras: str = ctx.input.get("system_hint", "")

    ticker_clause = ""
    if tickers:
        ticker_clause = f" for: {', '.join(t.upper() for t in tickers)}"

    prompt = _EARNINGS_PROMPT_TEMPLATE.format(
        days_back=days_back,
        ticker_clause=ticker_clause,
        max_items=max_items,
    )
    if prompt_extras:
        prompt = f"{prompt_extras.strip()}\n\n{prompt}"

    try:
        text = await ctx.call_llm(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.exception("actions-recent-earnings: LLM call failed")
        return RouteResult(text=f"Recent earnings failed: {exc}", ok=False, error="llm_error")

    return RouteResult(
        text=text,
        metadata={
            "route": "actions-recent-earnings",
            "tickers": tickers,
            "days_back": days_back,
        },
    )
