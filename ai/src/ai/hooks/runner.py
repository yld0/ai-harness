"""Ordered hook execution with total timeout; failures are isolated (Phase 7)."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from ai.hooks.auto_dream import AutoDreamHook
from ai.hooks.base import (
    Hook,
    HookConfig,
    HookContext,
    HookResult,
    load_hook_config,
)
from ai.hooks.compact import CompactHook
from ai.hooks.collapse import CollapseHook
from ai.hooks.skill_review import SkillReviewHook

logger = logging.getLogger(__name__)

_DEFAULT_HOOKS: dict[str, Hook] = {
    "compact": CompactHook(),
    "collapse": CollapseHook(),
    "auto_dream": AutoDreamHook(),
    "skill_review": SkillReviewHook(),
}


class HookRunner:
    """Post-response hooks including autonomous skill review (Phase 19)."""

    def __init__(
        self,
        config: HookConfig | None = None,
        hooks: dict[str, Hook] | None = None,
    ) -> None:
        self.config = config or load_hook_config()
        self._hooks = hooks or dict(_DEFAULT_HOOKS)

    async def run_after_response(self, ctx: HookContext) -> list[HookResult]:
        max_time = self.config.post_hook_timeout_s
        if not self.config.hooks_enabled:
            return []
        t0 = time.monotonic()

        async def _one(hook: Hook) -> HookResult:
            return await asyncio.to_thread(hook.run, ctx)

        results: list[HookResult] = []
        for name in self.config.hooks_enabled:
            remaining = max_time - (time.monotonic() - t0)
            if remaining <= 0:
                logger.warning("hook runner total timeout before hook %s", name)
                break
            hook = self._hooks.get(name)
            if hook is None:
                logger.warning("unknown hook: %s", name)
                continue
            try:
                res = await asyncio.wait_for(_one(hook), timeout=remaining)
            except Exception as exc:  # noqa: BLE001
                logger.exception("hook %s", name)
                results.append(
                    HookResult(
                        name=name,
                        ok=False,
                        detail=f"{type(exc).__name__}: {exc}",
                    )
                )
            else:
                results.append(res)
        return results
