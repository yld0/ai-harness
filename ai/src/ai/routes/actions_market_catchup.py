"""Route handler: actions-market-catchup.

Market-focused catch-up: summarise key moves, macro events, and
portfolio-relevant developments from the user's watchlists and tickers.
"""

from __future__ import annotations

import logging

from ai.routes.context import RouteContext, RouteResult

logger = logging.getLogger(__name__)

_MARKET_CATCHUP_PROMPT = """\
You are a financial assistant providing a market catch-up.

Review the financial memory context in your system prompt (tickers, watchlists, \
macro indicators) and provide a concise market update.

Instructions:
- Highlight notable price moves or macro events since the last update.
- Flag any watchlist items that may need attention.
- Mention any earnings or announcements that are upcoming or just passed.
- Keep the response to ≤400 words.
- Use bullet points grouped by: Market Overview, Watchlist, Upcoming Events.
- If data is unavailable, say so rather than speculating.
"""


async def run(ctx: RouteContext) -> RouteResult:
    prompt_extras = ctx.input.get("system_hint", "")
    prompt = _MARKET_CATCHUP_PROMPT
    if prompt_extras:
        prompt = f"{prompt_extras.strip()}\n\n{prompt}"

    try:
        text = await ctx.call_llm(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.exception("actions-market-catchup: LLM call failed")
        return RouteResult(text=f"Market catch-up failed: {exc}", ok=False, error="llm_error")

    return RouteResult(text=text, metadata={"route": "actions-market-catchup"})
