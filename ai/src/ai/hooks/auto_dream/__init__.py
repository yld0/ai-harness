"""auto_dream: gated periodic PARA memory consolidation (Claude-code-style cascade + background run)."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import date

from ai.config import HookConfig
from ai.hooks.types import Hook, HookContext, HookResult
from ai.memory.para import ParaMemoryLayout
from ai.hooks.auto_dream.consolidation_lock import (
    read_last_consolidated_at_ms,
    rollback_consolidation_lock,
    try_acquire_consolidation_lock,
)
from ai.hooks.auto_dream.daily_notes import count_daily_notes_touched_since
from ai.hooks.auto_dream.dream_runner import DreamRunner

logger = logging.getLogger(__name__)


async def _run_dream_then_cleanup(
    *,
    layout: ParaMemoryLayout,
    user_id: str,
    prior_mtime_ms: int,
    cfg: HookConfig,
    runner: DreamRunner,
) -> None:
    try:
        res = await runner.run(
            user_id,
            recent_daily_notes=cfg.AI_AUTO_DREAM_RECENT_DAILY_NOTES,
            dream_model_override=(cfg.AI_AUTO_DREAM_MODEL or "").strip() or None,
        )
        if not res.ok:
            rollback_consolidation_lock(layout, user_id, prior_mtime_ms)
            logger.warning(
                "auto_dream consolidated failed uid=%s detail=%s",
                user_id,
                res.detail,
            )
    except Exception:
        rollback_consolidation_lock(layout, user_id, prior_mtime_ms)
        logger.exception("auto_dream background failure")


class AutoDreamHook:
    """Fire-and-forget memory consolidation after cheap gate cascade."""

    name: str = "auto_dream"

    def __init__(
        self,
        *,
        runner: DreamRunner | None = None,
        layout: ParaMemoryLayout | None = None,
    ) -> None:
        self._runner = runner
        self._layout = layout
        self._pending: set[str] = set()
        self._lock = threading.Lock()
        self._last_scan_monotonic: dict[str, float] = {}

    def _get_layout(self) -> ParaMemoryLayout:
        if self._layout is not None:
            return self._layout
        return ParaMemoryLayout()

    def _get_runner(self) -> DreamRunner:
        if self._runner is not None:
            return self._runner
        return DreamRunner()

    def run(self, ctx: HookContext) -> HookResult:
        cfg = ctx.config
        if not cfg.AI_AUTO_DREAM_ENABLED:
            return HookResult(name=self.name, ok=True, detail="disabled")

        layout = self._get_layout()
        uid = ctx.user_id
        try:
            last_ms = read_last_consolidated_at_ms(layout, uid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("auto_dream read_last_consolidated_at: %s", exc)
            return HookResult(name=self.name, ok=True, detail="read_timestamp_failed")

        hours_since = (time.time() * 1000.0 - last_ms) / 3_600_000.0
        if hours_since < cfg.AI_AUTO_DREAM_MIN_HOURS:
            return HookResult(
                name=self.name,
                ok=True,
                detail="time_gate",
                data={"hours_since": round(hours_since, 2)},
            )

        mono_now = time.monotonic()
        last_scan = self._last_scan_monotonic.get(uid, 0.0)
        throttle_s = float(cfg.AI_AUTO_DREAM_SCAN_THROTTLE_S)
        if throttle_s > 0 and mono_now - last_scan < throttle_s:
            return HookResult(
                name=self.name,
                ok=True,
                detail="scan_throttle",
                data={
                    "since_last_scan_s": round(mono_now - last_scan, 1),
                    "throttle_s": throttle_s,
                },
            )
        self._last_scan_monotonic[uid] = mono_now

        today = date.today().isoformat()
        try:
            n_sessions = count_daily_notes_touched_since(
                layout,
                uid,
                since_ms=last_ms,
                exclude_day=today,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("auto_dream session count failed: %s", exc)
            return HookResult(name=self.name, ok=True, detail="session_gate_scan_failed")

        if n_sessions < cfg.AI_AUTO_DREAM_MIN_SESSIONS:
            return HookResult(
                name=self.name,
                ok=True,
                detail="session_gate",
                data={"sessions_since": n_sessions, "needed": cfg.AI_AUTO_DREAM_MIN_SESSIONS},
            )

        with self._lock:
            if uid in self._pending:
                return HookResult(name=self.name, ok=True, detail="already_pending")
            self._pending.add(uid)

        prior: int | None = None
        try:
            prior = try_acquire_consolidation_lock(layout, uid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("auto_dream lock acquire error: %s", exc)
            with self._lock:
                self._pending.discard(uid)
            return HookResult(name=self.name, ok=True, detail="lock_acquire_error")
            with self._lock:
                self._pending.discard(uid)
            return HookResult(name=self.name, ok=True, detail="lock_held")

        runner = self._get_runner()
        prior_ms = prior

        async def dream_task() -> None:
            await _run_dream_then_cleanup(
                layout=layout,
                user_id=uid,
                prior_mtime_ms=prior_ms,
                cfg=cfg,
                runner=runner,
            )

        def thread_fn() -> None:
            try:
                asyncio.run(dream_task())
            except Exception:  # noqa: BLE001
                logger.exception("auto_dream background failed uid=%s", uid[:8])
            finally:
                with self._lock:
                    self._pending.discard(uid)

        threading.Thread(target=thread_fn, daemon=True, name=f"auto-dream-{uid[:8]}").start()

        return HookResult(
            name=self.name,
            ok=True,
            detail="dream_dispatched",
            data={
                "sessions_since": n_sessions,
                "hours_since": round(hours_since, 2),
                "prior_mtime_ms": prior_ms,
            },
        )
