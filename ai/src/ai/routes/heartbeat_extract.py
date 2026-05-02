"""Route handler: heartbeat-extract.

Per-entity catch-up + fact extraction via LLM.  For each entity found under
the user's life directory the handler:

1. Reads the current summary.md (or items.yaml fallback) as context.
2. Calls ``call_llm`` with an extraction prompt requesting new MemoryFact
   candidates.
3. Appends a dated note to the user's daily memory journal.

The LLM output is stored as a plain daily note rather than parsed into
structured facts — parsing can be refined in later phases.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
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

_EXTRACT_PROMPT = """\
You are an information-extraction assistant.  Below is the current memory for \
the entity "{entity_id}" (kind: {kind}).

---
{context}
---

Based on this, extract any new facts that should be added to the memory.
Return a brief bullet list of NEW observations only (skip anything already stated).
If there is nothing new, respond: "No new facts."
"""


def _read_entity_context(entity_dir: Path) -> str:
    """Read summary.md if present, otherwise first 2000 chars of items.yaml."""
    summary_path = entity_dir / "summary.md"
    if summary_path.is_file():
        return summary_path.read_text("utf-8")[:3000]
    items_path = entity_dir / "items.yaml"
    if items_path.is_file():
        return items_path.read_text("utf-8")[:3000]
    return "(no context available)"


async def run(ctx: RouteContext) -> RouteResult:
    today = date.fromisoformat(ctx.input.get("date", date.today().isoformat()))
    # Optional filter: only process entities matching a specific kind
    only_kind: str | None = ctx.input.get("kind")

    user_root = ctx.layout.user_root(ctx.user_id)
    life_root = user_root / "life"

    entities_processed = 0
    entities_failed = 0

    for kind in _ENTITY_KINDS:
        if only_kind and kind != only_kind:
            continue
        kind_dir = life_root / kind
        if not kind_dir.is_dir():
            continue
        for entity_dir in sorted(kind_dir.iterdir()):
            if not entity_dir.is_dir():
                continue
            entity_id = entity_dir.name
            try:
                context_text = _read_entity_context(entity_dir)
                prompt = _EXTRACT_PROMPT.format(
                    entity_id=entity_id,
                    kind=kind,
                    context=context_text,
                )
                extraction = await ctx.call_llm(prompt)
                if extraction.strip() and extraction.strip() != "No new facts.":
                    note = f"[heartbeat-extract] {kind}/{entity_id}:\n{extraction.strip()}"
                    ctx.writer.append_daily_note(
                        ctx.user_id,
                        note,
                        day=today,
                        now=datetime.now(timezone.utc),
                    )
                entities_processed += 1
                logger.debug("heartbeat-extract: %s/%s — ok", kind, entity_id)
            except Exception as exc:  # noqa: BLE001
                entities_failed += 1
                logger.warning("heartbeat-extract: %s/%s failed: %s", kind, entity_id, exc)

    summary = f"Heartbeat extract complete: {entities_processed} entities processed" + (f", {entities_failed} failed" if entities_failed else "") + "."
    return RouteResult(
        text=summary,
        metadata={
            "entities_processed": entities_processed,
            "entities_failed": entities_failed,
            "date": today.isoformat(),
        },
    )
