"""Collapse: drop oldest user/assistant turns over a hard threshold; keep first system + recent window."""

from __future__ import annotations

import logging
from typing import Sequence

from ai.agent.loop import ProviderMessage
from ai.hooks.types import Hook, HookContext, HookResult
from ai.config import HookConfig

logger = logging.getLogger(__name__)


def estimate_message_chars(messages: Sequence[ProviderMessage]) -> int:
    return sum(len(m.content) for m in messages)


def collapse_messages(
    messages: list[ProviderMessage],
    *,
    hard_threshold: int,
    keep_recent_pairs: int,
) -> list[ProviderMessage]:
    """
    If over `hard_threshold` chars, keep the first system message (if present) and the last
    `keep_recent_pairs` * 2` non-system messages (approx. user/assistant pairs).
    """
    if not messages:
        return []
    if estimate_message_chars(messages) <= hard_threshold:
        return list(messages)
    if messages[0].role != "system":
        return list(messages)
    first = messages[0]
    rest = messages[1:]
    cap = min(len(rest), max(1, keep_recent_pairs * 2))
    tail = rest[-cap:]
    return [first, *tail]


class CollapseHook:
    name: str = "collapse"

    def run(self, ctx: HookContext) -> HookResult:
        cfg: HookConfig = ctx.config
        if not ctx.messages:
            return HookResult(name=self.name, ok=True, detail="no_messages")
        try:
            out = collapse_messages(
                list(ctx.messages),
                hard_threshold=cfg.AI_COLLAPSE_HARD_CHARS,
                keep_recent_pairs=cfg.AI_COLLAPSE_KEEP_PAIRS,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("collapse hook")
            return HookResult(name=self.name, ok=False, detail=f"{type(exc).__name__}: {exc}")
        return HookResult(
            name=self.name,
            ok=True,
            data={
                "in_len": len(ctx.messages),
                "out_len": len(out),
                "system_preserved": bool(out) and out[0].role == "system",
            },
        )
