"""Route handler: spaces-compact.

Runs the weekly synthesis (Phase 4) restricted to a single space's items.yaml,
then regenerates the knowledge-base.md from the updated summary.

Input keys:
  - ``space_id``: str — required.
  - ``date``: str — ISO date for decay calculation (defaults to today).
"""

from __future__ import annotations

import logging
from datetime import date

from ai.routes.context import RouteContext, RouteResult

logger = logging.getLogger(__name__)


async def run(ctx: RouteContext) -> RouteResult:
    space_id = ctx.input.get("space_id")
    if not space_id:
        return RouteResult(text="space_id is required.", ok=False, error="missing_input")

    today_str = ctx.input.get("date", date.today().isoformat())
    today = date.fromisoformat(today_str)

    try:
        ctx.writer.synthesize_summary(ctx.user_id, kind="spaces", entity_id=space_id, today=today)
    except Exception as exc:  # noqa: BLE001
        logger.exception("spaces-compact: synthesis failed for %s", space_id)
        return RouteResult(text=f"Compact failed: {exc}", ok=False, error="synthesis_error")

    # Optionally regenerate knowledge-base.md from the new summary
    try:
        space_dir = ctx.layout.entity_dir(ctx.user_id, "spaces", space_id)
    except Exception as exc:
        return RouteResult(text=f"Invalid space_id: {exc}", ok=False, error="invalid_space_id")

    summary_path = space_dir / "summary.md"
    kb_path = space_dir / "knowledge-base.md"

    if summary_path.is_file():
        summary_content = summary_path.read_text("utf-8")
        kb_prompt = f"Rewrite the following space summary as a concise knowledge base in Markdown.\n\n" f"---\n{summary_content[:4000]}\n---"
        try:
            kb_content = await ctx.call_llm(kb_prompt)
            kb_path.write_text(kb_content, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning("spaces-compact: KB regeneration failed: %s", exc)
            # Non-fatal — synthesis succeeded

    return RouteResult(
        text=f"Space {space_id!r} compacted for {today_str}.",
        metadata={"space_id": space_id, "date": today_str},
    )
