"""Route handler: monitors-check.

Reads the user's MONITORS.md checklist and processes each monitoring item
via LLM, appending findings to the daily memory journal.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

from ai.routes.context import RouteContext, RouteResult

logger = logging.getLogger(__name__)

MONITORS_FILE = "MONITORS.md"
MONITORS_DIR = "monitors"

_CHECK_PROMPT = """\
You are a monitoring assistant. The user has asked you to periodically check \
the following item:

---
{item_content}
---

Based on current information available to you, evaluate this monitoring item. \
Provide a concise status update. If the condition described has been met or \
something notable has occurred, clearly flag it. If nothing has changed, say \
"No change."
"""

_HEADING_RE = re.compile(r"^## ", re.MULTILINE)


def _parse_items(content: str) -> list[str]:
    """Split MONITORS.md into individual items by ## headings."""
    parts = _HEADING_RE.split(content)
    return [f"## {part.strip()}" for part in parts[1:] if part.strip()]


async def run(ctx: RouteContext) -> RouteResult:
    """Process each monitoring item and log findings."""
    today = date.fromisoformat(ctx.input.get("date", date.today().isoformat()))

    user_root = ctx.layout.user_root(ctx.user_id)
    monitors_path = user_root / "life" / MONITORS_DIR / MONITORS_FILE

    if not monitors_path.is_file():
        return RouteResult(
            text="No monitoring checklist found.",
            metadata={"items_checked": 0},
        )

    content = monitors_path.read_text("utf-8")
    items = _parse_items(content)

    if not items:
        return RouteResult(
            text="Monitoring checklist is empty.",
            metadata={"items_checked": 0},
        )

    items_checked = 0
    items_flagged = 0
    items_failed = 0

    for item_content in items:
        try:
            prompt = _CHECK_PROMPT.format(item_content=item_content)
            result = await ctx.call_llm(prompt)
            result_stripped = result.strip()

            if result_stripped and result_stripped != "No change.":
                heading = item_content.split("\n", 1)[0].strip()
                note = f"[monitors-check] {heading}:\n{result_stripped}"
                ctx.writer.append_daily_note(
                    ctx.user_id,
                    note,
                    day=today,
                    now=datetime.now(timezone.utc),
                )
                items_flagged += 1

            items_checked += 1
        except Exception as exc:
            items_failed += 1
            logger.warning("monitors-check: item failed: %s", exc)

    summary = (
        f"Monitors check complete: {items_checked} items checked, "
        f"{items_flagged} flagged"
        + (f", {items_failed} failed" if items_failed else "")
        + "."
    )
    return RouteResult(
        text=summary,
        metadata={
            "items_checked": items_checked,
            "items_flagged": items_flagged,
            "items_failed": items_failed,
            "date": today.isoformat(),
        },
    )
