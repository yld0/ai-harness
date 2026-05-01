"""Route handler: actions-catchup.

General catch-up: summarise what happened since the user was last active,
drawing from recent daily notes and the hot memory snapshot.
"""

from __future__ import annotations

import logging

from ai.routes.context import RouteContext, RouteResult

logger = logging.getLogger(__name__)

_CATCHUP_PROMPT = """\
You are a personal assistant providing a catch-up summary.

The user has been away and wants to know what has changed since they were last \
active.  Use the memory context already included in your system prompt to \
identify the most important recent developments.

Instructions:
- Summarise the top 3–5 things the user should know about.
- Keep the response concise (≤300 words).
- Use bullet points.
- If nothing notable happened, say so clearly.
"""


async def run(ctx: RouteContext) -> RouteResult:
    prompt_extras = ctx.input.get("system_hint", "")
    prompt = _CATCHUP_PROMPT
    if prompt_extras:
        prompt = f"{prompt_extras.strip()}\n\n{prompt}"

    try:
        text = await ctx.call_llm(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.exception("actions-catchup: LLM call failed")
        return RouteResult(text=f"Catch-up failed: {exc}", ok=False, error="llm_error")

    return RouteResult(text=text, metadata={"route": "actions-catchup"})
