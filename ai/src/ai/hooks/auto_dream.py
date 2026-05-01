"""auto_dream: append PARA daily notes and light fact extraction on a turn cadence (Phase 4 writer)."""

from __future__ import annotations

import logging
import re
from datetime import date

from ai.memory.schemas import MemoryFact, Validity
from ai.memory.writer import MemoryWriter
from ai.hooks.base import Hook, HookContext, HookResult

logger = logging.getLogger(__name__)

_ENTITY_RE = re.compile(r"\b([A-Z]{1,5})\b")


class AutoDreamHook:
    name: str = "auto_dream"

    def __init__(self, writer: MemoryWriter | None = None) -> None:
        self._writer = writer or MemoryWriter()

    def run(self, ctx: HookContext) -> HookResult:
        n = ctx.config.auto_dream_every_n_turns
        if n <= 0 or ctx.turn_index == 0 or ctx.turn_index % n != 0:
            return HookResult(name=self.name, ok=True, detail="skipped_cadence")
        try:
            line = f"user: {ctx.user_message[:500]}\nassistant: {ctx.response_text[:500]}\n"
            self._writer.append_daily_note(ctx.user_id, line)
            tickers = {m.group(1) for m in _ENTITY_RE.finditer(ctx.user_message) if 1 < len(m.group(1)) < 5}
            if tickers:
                sym = sorted(tickers)[0]
                fact = MemoryFact(
                    id=f"auto_dream_{ctx.conversation_id}_{ctx.turn_index}",
                    fact=f"Session note involving {sym}",
                    validity=Validity.EVERGREEN,
                    recorded_at=date.today(),
                )
                self._writer.write_fact(
                    ctx.user_id,
                    kind="tickers",
                    entity_id=sym,
                    fact=fact,
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("auto_dream hook")
            return HookResult(name=self.name, ok=False, detail=f"{type(exc).__name__}: {exc}")
        return HookResult(name=self.name, ok=True, data={"wrote_note": True})
