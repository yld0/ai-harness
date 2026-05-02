"""Compact: summarize middle turns when over a soft size threshold (system prefix preserved in placement)."""

from __future__ import annotations

import logging
from typing import Callable, Sequence

from ai.agent.loop import ProviderMessage
from ai.hooks.types import Hook, HookContext, HookResult
from ai.config import HookConfig

logger = logging.getLogger(__name__)


def estimate_message_chars(messages: Sequence[ProviderMessage]) -> int:
    return sum(len(m.content) for m in messages)


def compact_messages(
    messages: list[ProviderMessage],
    *,
    soft_threshold: int,
    summarizer: Callable[[list[ProviderMessage]], str] | None = None,
) -> list[ProviderMessage]:
    """Replace middle messages (between first and last) with one assistant \"summary\" turn."""
    if len(messages) < 3:
        return list(messages)
    if estimate_message_chars(messages) <= soft_threshold:
        return list(messages)
    first, last = messages[0], messages[-1]
    middle = list(messages[1:-1])
    text = summarizer(middle) if summarizer is not None else "[Session compacted: prior turns summarized]"
    summary = ProviderMessage(role="assistant", content=text)
    return [first, summary, last]


class CompactHook:
    name: str = "compact"

    def run(self, ctx: HookContext) -> HookResult:
        cfg: HookConfig = ctx.config
        if not ctx.messages:
            return HookResult(name=self.name, ok=True, detail="no_messages")
        try:
            out = compact_messages(
                list(ctx.messages),
                soft_threshold=cfg.AI_COMPACT_SOFT_CHARS,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("compact hook")
            return HookResult(name=self.name, ok=False, detail=f"{type(exc).__name__}: {exc}")
        return HookResult(
            name=self.name,
            ok=True,
            data={"in_len": len(ctx.messages), "out_len": len(out)},
        )
