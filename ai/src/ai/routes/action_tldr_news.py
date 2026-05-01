"""Route handler: action-tldr-news.

Produces a TLDR-style news digest, optionally filtered by topic or source.
Input keys (all optional):
  - ``topics``: list[str] — topics to focus on.
  - ``max_items``: int — max number of news items (default 5).
  - ``system_hint``: str — extra system context.
"""

from __future__ import annotations

import logging

from ai.routes.context import RouteContext, RouteResult

logger = logging.getLogger(__name__)

_TLDR_PROMPT_TEMPLATE = """\
You are a news digest assistant.

Provide a TLDR news summary{topic_clause}.
Limit to {max_items} items.

Instructions:
- Each item: one headline sentence + one sentence of context.
- Order by importance (most impactful first).
- Do not speculate beyond what is in your context.
- If there is no relevant news, say "Nothing notable today."
"""


async def run(ctx: RouteContext) -> RouteResult:
    topics: list[str] = ctx.input.get("topics", [])
    max_items: int = int(ctx.input.get("max_items", 5))
    prompt_extras: str = ctx.input.get("system_hint", "")

    topic_clause = ""
    if topics:
        topic_clause = f" focused on: {', '.join(topics)}"

    prompt = _TLDR_PROMPT_TEMPLATE.format(topic_clause=topic_clause, max_items=max_items)
    if prompt_extras:
        prompt = f"{prompt_extras.strip()}\n\n{prompt}"

    try:
        text = await ctx.call_llm(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.exception("action-tldr-news: LLM call failed")
        return RouteResult(text=f"TLDR news failed: {exc}", ok=False, error="llm_error")

    return RouteResult(
        text=text,
        metadata={
            "route": "action-tldr-news",
            "topics": topics,
            "max_items": max_items,
        },
    )
