"""SkillReviewHook — spawns a background skill proposal after N tool calls (Phase 19).

Design constraints
------------------
- Must NOT block the main response path (hook runner timeout budget).
- Two rapid threshold crossings must not spawn duplicate background tasks
  (dedupe flag per (user_id, conversation_id)).
- All file writes go through ReviewRunner which uses guarded_user_path — no
  writes outside the user memory root.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from ai.hooks.types import Hook, HookContext, HookResult
from ai.skills.review_runner import ReviewRunner

logger = logging.getLogger(__name__)


def _count_tool_calls(messages: list[Any]) -> int:
    """Count messages with role='tool' (works for ProviderMessage and plain dicts)."""
    count = 0
    for msg in messages:
        role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else None)
        if role == "tool":
            count += 1
    return count


class SkillReviewHook:
    """Post-response hook that triggers a background skill review after N tool calls.

    Parameters
    ----------
    runner:
        `ReviewRunner` instance.  If *None*, one is constructed lazily on first
        use so the import cost is deferred and tests can inject fakes.
    threshold:
        Override the threshold at construction time.  When *None*, falls back to
        ``ctx.config.skill_review_threshold`` at run time.
    """

    name: str = "skill_review"

    def __init__(
        self,
        runner: Any | None = None,
        threshold: int | None = None,
    ) -> None:
        self._runner = runner
        self._threshold_override = threshold
        # (user_id, conversation_id) -> True when a review task is already pending
        self._pending: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    def _get_runner(self) -> Any:
        if self._runner is not None:
            return self._runner
        return ReviewRunner()

    def _effective_threshold(self, ctx: HookContext) -> int:
        if self._threshold_override is not None:
            return self._threshold_override
        return ctx.config.AI_SKILL_REVIEW_THRESHOLD

    def run(self, ctx: HookContext) -> HookResult:
        threshold = self._effective_threshold(ctx)
        if threshold <= 0:
            return HookResult(name=self.name, ok=True, detail="disabled")

        tool_count = _count_tool_calls(ctx.messages)
        if tool_count < threshold:
            return HookResult(
                name=self.name,
                ok=True,
                detail="below_threshold",
                data={"tool_count": tool_count, "threshold": threshold},
            )

        key = (ctx.user_id, ctx.conversation_id)
        with self._lock:
            if key in self._pending:
                return HookResult(
                    name=self.name,
                    ok=True,
                    detail="already_pending",
                    data={"tool_count": tool_count},
                )
            self._pending.add(key)

        # Spawn background review — must not block.
        runner = self._get_runner()
        coro = runner.run(
            user_id=ctx.user_id,
            user_message=ctx.user_message,
            response_text=ctx.response_text,
            messages=ctx.messages,
            skill_review_model=ctx.config.AI_SKILL_REVIEW_MODEL,
        )
        thread = threading.Thread(
            target=_run_in_new_loop,
            args=(coro, key, self._pending, self._lock),
            daemon=True,
            name=f"skill-review-{ctx.user_id[:8]}",
        )
        thread.start()

        return HookResult(
            name=self.name,
            ok=True,
            detail="review_dispatched",
            data={"tool_count": tool_count, "threshold": threshold},
        )


def _run_in_new_loop(
    coro: Any,
    key: tuple[str, str],
    pending: set[tuple[str, str]],
    lock: threading.Lock,
) -> None:
    """Run *coro* in a fresh event loop; clear pending flag when done."""
    try:
        asyncio.run(coro)
    except Exception:  # noqa: BLE001
        logger.exception("background skill review failed for %s", key)
    finally:
        with lock:
            pending.discard(key)
