"""Route handler: memory-decay-tick.

Walks every items.yaml under a user's life directory, applies
``update_decay_state`` to each fact, rewrites the file if anything changed,
and flips expired facts to status=historical.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import yaml

from ai.memory.decay import update_decay_state
from ai.memory.schemas import MemoryFact
from ai.routes.context import RouteContext, RouteResult

logger = logging.getLogger(__name__)


def _read_facts(path: Path) -> list[MemoryFact]:
    if not path.is_file():
        return []
    try:
        raw = yaml.safe_load(path.read_text("utf-8"))
        if not isinstance(raw, list):
            return []
        return [MemoryFact.model_validate(item) for item in raw]
    except Exception:  # noqa: BLE001
        logger.warning("decay_tick: could not parse %s", path)
        return []


def _write_facts(path: Path, facts: list[MemoryFact]) -> None:
    data = [f.model_dump(mode="json", exclude_none=True) for f in facts]
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


async def run(ctx: RouteContext) -> RouteResult:
    today: date = date.fromisoformat(ctx.input.get("date", date.today().isoformat()))
    user_root = ctx.layout.user_root(ctx.user_id)
    life_root = user_root / "life"
    if not life_root.is_dir():
        return RouteResult(
            text="No life directory found — nothing to decay.",
            metadata={"files_updated": 0},
        )

    files_checked = 0
    files_updated = 0
    facts_transitioned = 0

    for items_path in sorted(life_root.rglob("items.yaml")):
        files_checked += 1
        original = _read_facts(items_path)
        if not original:
            continue
        updated = [update_decay_state(f, today=today) for f in original]
        transitions = sum(1 for old, new in zip(original, updated) if old.status != new.status)
        changed = transitions > 0 or any(old.score != new.score for old, new in zip(original, updated))
        if changed:
            _write_facts(items_path, updated)
            files_updated += 1
            facts_transitioned += transitions
            logger.debug("decay_tick: updated %s (%d transitions)", items_path, transitions)

    summary = (
        f"Decay tick complete: {files_checked} files checked, "
        f"{files_updated} updated, {facts_transitioned} facts transitioned to historical."
    )
    logger.info(summary)
    return RouteResult(
        text=summary,
        metadata={
            "files_checked": files_checked,
            "files_updated": files_updated,
            "facts_transitioned": facts_transitioned,
            "date": today.isoformat(),
        },
    )
