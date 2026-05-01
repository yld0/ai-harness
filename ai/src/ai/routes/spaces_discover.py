"""Route handler: spaces-discover.

Discovers and suggests new knowledge sources for a space, using LLM reasoning
over the existing knowledge base and topic description.

Input keys:
  - ``space_id``: str — required.
  - ``topic``: str — optional topic hint to focus discovery.
  - ``max_suggestions``: int — max number of source suggestions (default 5).
"""

from __future__ import annotations

import logging

from ai.routes.context import RouteContext, RouteResult

logger = logging.getLogger(__name__)

_DISCOVER_PROMPT_TEMPLATE = """\
You are a research assistant helping to discover knowledge sources.

Space: "{space_id}"
{topic_line}

Current knowledge base:
---
{kb_content}
---

Suggest {max_suggestions} high-quality sources (websites, feeds, databases) \
that would complement or expand this space.

For each suggestion:
- Name and URL (use plausible real sources)
- Why it is relevant
- Recommended timingValidity: evergreen | daily | weekly | event_driven

Format as a numbered list.
"""


async def run(ctx: RouteContext) -> RouteResult:
    space_id = ctx.input.get("space_id")
    if not space_id:
        return RouteResult(text="space_id is required.", ok=False, error="missing_input")

    topic: str = ctx.input.get("topic", "")
    max_suggestions: int = int(ctx.input.get("max_suggestions", 5))

    try:
        space_dir = ctx.layout.entity_dir(ctx.user_id, "spaces", space_id)
    except Exception as exc:
        return RouteResult(text=f"Invalid space_id: {exc}", ok=False, error="invalid_space_id")

    kb_path = space_dir / "knowledge-base.md"
    kb_content = kb_path.read_text("utf-8")[:3000] if kb_path.is_file() else "(empty)"
    topic_line = f"Topic focus: {topic}" if topic else ""

    prompt = _DISCOVER_PROMPT_TEMPLATE.format(
        space_id=space_id,
        topic_line=topic_line,
        kb_content=kb_content,
        max_suggestions=max_suggestions,
    )

    try:
        text = await ctx.call_llm(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.exception("spaces-discover: LLM call failed")
        return RouteResult(text=f"Discovery failed: {exc}", ok=False, error="llm_error")

    return RouteResult(
        text=text,
        metadata={
            "space_id": space_id,
            "topic": topic,
            "max_suggestions": max_suggestions,
        },
    )
