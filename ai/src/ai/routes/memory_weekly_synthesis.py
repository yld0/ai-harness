"""Route handler: memory-weekly-synthesis.

Rebuilds summary.md from active facts in items.yaml for every entity
found under the user's life directory.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from ai.memory.para import MemoryEntityKind
from ai.routes.context import RouteContext, RouteResult

logger = logging.getLogger(__name__)

_ENTITY_KINDS: tuple[MemoryEntityKind, ...] = (
    "tickers",
    "sectors",
    "spaces",
    "watchlists",
    "people",
    "macros",
)


async def run(ctx: RouteContext) -> RouteResult:
    today_str: str = ctx.input.get("date", date.today().isoformat())
    today = date.fromisoformat(today_str)
    user_root = ctx.layout.user_root(ctx.user_id)
    life_root = user_root / "life"

    entities_processed = 0
    entities_failed = 0

    for kind in _ENTITY_KINDS:
        kind_dir = life_root / kind
        if not kind_dir.is_dir():
            continue
        for entity_dir in sorted(kind_dir.iterdir()):
            if not entity_dir.is_dir():
                continue
            entity_id = entity_dir.name
            try:
                ctx.writer.synthesize_summary(ctx.user_id, kind=kind, entity_id=entity_id, today=today)
                entities_processed += 1
                logger.debug("synthesis: %s/%s — ok", kind, entity_id)
            except Exception as exc:  # noqa: BLE001
                entities_failed += 1
                logger.warning("synthesis: %s/%s failed: %s", kind, entity_id, exc)

    summary = (
        f"Weekly synthesis complete: {entities_processed} entities updated"
        + (f", {entities_failed} failed" if entities_failed else "")
        + "."
    )
    logger.info(summary)
    return RouteResult(
        text=summary,
        metadata={
            "entities_processed": entities_processed,
            "entities_failed": entities_failed,
            "date": today.isoformat(),
        },
    )
