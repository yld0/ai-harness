"""Tests for auto_dream hook gate cascade."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

from ai.config import hook_config
from ai.hooks.auto_dream import AutoDreamHook
from ai.hooks.types import HookContext
from ai.memory.para import ParaMemoryLayout
from ai.hooks.auto_dream.dream_runner import DreamRunner


def _minimal_ctx(*, cfg, user_id: str = "u1", conv_id: str = "c1") -> HookContext:
    return HookContext(
        user_id=user_id,
        conversation_id=conv_id,
        user_message="hi",
        response_text="bye",
        request=MagicMock(),
        messages=[],
        config=cfg,
        turn_index=5,
    )


def test_disabled(tmp_path: Path) -> None:
    layout = ParaMemoryLayout(memory_root=tmp_path / "m")
    cfg = replace(hook_config, AI_AUTO_DREAM_ENABLED=False)
    hook = AutoDreamHook(layout=layout)
    r = hook.run(_minimal_ctx(cfg=cfg))
    assert r.detail == "disabled"


def test_time_gate(tmp_path: Path) -> None:
    import time

    layout = ParaMemoryLayout(memory_root=tmp_path / "m")
    uid = "user1"
    cfg = replace(
        hook_config,
        AI_AUTO_DREAM_ENABLED=True,
        AI_AUTO_DREAM_MIN_HOURS=24,
        AI_AUTO_DREAM_MIN_SESSIONS=1,
        AI_AUTO_DREAM_SCAN_THROTTLE_S=0,
    )
    hook = AutoDreamHook(layout=layout)
    recent_ms = time.time() * 1000.0
    with patch("ai.hooks.auto_dream.read_last_consolidated_at_ms", return_value=recent_ms):
        r = hook.run(_minimal_ctx(cfg=cfg, user_id=uid))
    assert r.detail == "time_gate"


def test_scan_throttle(tmp_path: Path) -> None:
    import time

    layout = ParaMemoryLayout(memory_root=tmp_path / "m")
    uid = "user1"
    cfg = replace(
        hook_config,
        AI_AUTO_DREAM_ENABLED=True,
        AI_AUTO_DREAM_MIN_HOURS=0,
        AI_AUTO_DREAM_MIN_SESSIONS=0,
        AI_AUTO_DREAM_SCAN_THROTTLE_S=3600,
    )
    hook = AutoDreamHook(layout=layout)
    hook._last_scan_monotonic[uid] = time.monotonic()
    with patch("ai.hooks.auto_dream.read_last_consolidated_at_ms", return_value=0.0):
        r = hook.run(_minimal_ctx(cfg=cfg, user_id=uid))
    assert r.detail == "scan_throttle"


def test_session_gate(tmp_path: Path) -> None:
    layout = ParaMemoryLayout(memory_root=tmp_path / "m")
    uid = "user1"
    layout.ensure_user_layout(uid)
    cfg = replace(
        hook_config,
        AI_AUTO_DREAM_ENABLED=True,
        AI_AUTO_DREAM_MIN_HOURS=0,
        AI_AUTO_DREAM_MIN_SESSIONS=10,
        AI_AUTO_DREAM_SCAN_THROTTLE_S=0,
    )
    hook = AutoDreamHook(layout=layout)
    with patch("ai.hooks.auto_dream.read_last_consolidated_at_ms", return_value=0.0):
        r = hook.run(_minimal_ctx(cfg=cfg, user_id=uid))
    assert r.detail == "session_gate"
    assert r.data.get("sessions_since", 0) < 10


def test_already_pending(tmp_path: Path) -> None:
    layout = ParaMemoryLayout(memory_root=tmp_path / "m")
    uid = "user1"
    cfg = replace(
        hook_config,
        AI_AUTO_DREAM_ENABLED=True,
        AI_AUTO_DREAM_MIN_HOURS=0,
        AI_AUTO_DREAM_MIN_SESSIONS=0,
        AI_AUTO_DREAM_SCAN_THROTTLE_S=0,
    )
    hook = AutoDreamHook(layout=layout)
    hook._pending.add(uid)
    with patch("ai.hooks.auto_dream.read_last_consolidated_at_ms", return_value=0.0):
        with patch("ai.hooks.auto_dream.count_daily_notes_touched_since", return_value=5):
            r = hook.run(_minimal_ctx(cfg=cfg, user_id=uid))
    hook._pending.discard(uid)
    assert r.detail == "already_pending"


def test_dream_dispatched_starts_thread(tmp_path: Path) -> None:
    layout = ParaMemoryLayout(memory_root=tmp_path / "m")
    uid = "user1"
    layout.ensure_user_layout(uid)
    mem = layout.guarded_user_path(uid, "memory")
    for d in ("2025-05-01", "2025-05-02", "2025-05-03", "2025-05-04", "2025-05-05"):
        (mem / f"{d}.md").write_text("x", encoding="utf-8")
    cfg = replace(
        hook_config,
        AI_AUTO_DREAM_ENABLED=True,
        AI_AUTO_DREAM_MIN_HOURS=0,
        AI_AUTO_DREAM_MIN_SESSIONS=1,
        AI_AUTO_DREAM_SCAN_THROTTLE_S=0,
    )
    runner = MagicMock(spec=DreamRunner)
    hook = AutoDreamHook(runner=runner, layout=layout)
    with patch("ai.hooks.auto_dream.read_last_consolidated_at_ms", return_value=0.0):
        with patch("ai.hooks.auto_dream.try_acquire_consolidation_lock", return_value=0):
            with patch("ai.hooks.auto_dream.threading.Thread") as thread_cls:
                r = hook.run(_minimal_ctx(cfg=cfg, user_id=uid))
                assert thread_cls.call_count == 1
                assert r.detail == "dream_dispatched"
