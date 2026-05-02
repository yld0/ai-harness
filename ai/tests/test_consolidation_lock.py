"""Tests for consolidation lock acquire, verify, reclaim, and rollback."""

from __future__ import annotations

import os
import time
from pathlib import Path

import math
from ai.memory.para import ParaMemoryLayout
from ai.hooks.auto_dream.consolidation_lock import (
    HOLDER_STALE_MS,
    read_last_consolidated_at_ms,
    rollback_consolidation_lock,
    try_acquire_consolidation_lock,
)


def _touch_lock(path: Path, *, mtime_epoch_s: float, body: str = "1") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    os.utime(path, (mtime_epoch_s, mtime_epoch_s))


def test_read_last_absent(tmp_path: Path) -> None:
    layout = ParaMemoryLayout(memory_root=tmp_path / "m")
    uid = "user1"
    assert read_last_consolidated_at_ms(layout, uid) == 0.0


def test_acquire_and_sets_holder(tmp_path: Path) -> None:
    layout = ParaMemoryLayout(memory_root=tmp_path / "m")
    uid = "user1"
    prior = try_acquire_consolidation_lock(layout, uid)
    assert prior == 0
    last = read_last_consolidated_at_ms(layout, uid)
    assert last > 0


def test_blocked_while_holder_live(tmp_path: Path) -> None:
    layout = ParaMemoryLayout(memory_root=tmp_path / "m")
    uid = "user1"
    assert try_acquire_consolidation_lock(layout, uid) == 0
    assert try_acquire_consolidation_lock(layout, uid) is None


def test_reclaim_dead_pid_stale_mtime(tmp_path: Path) -> None:
    layout = ParaMemoryLayout(memory_root=tmp_path / "m")
    uid = "user1"
    path = tmp_path / "m" / "users" / uid / "memory" / ".consolidate-lock"
    old_t = time.time() - (HOLDER_STALE_MS / 1000.0 + 60.0)
    _touch_lock(path, mtime_epoch_s=old_t, body="999999001")
    prior = try_acquire_consolidation_lock(layout, uid)
    assert math.isclose(prior, old_t * 1000.0, rel_tol=0.0, abs_tol=5.0)
    assert path.read_text(encoding="utf-8").strip() == str(os.getpid())


def test_rollback_unlink_when_prior_zero(tmp_path: Path) -> None:
    layout = ParaMemoryLayout(memory_root=tmp_path / "m")
    uid = "user1"
    assert try_acquire_consolidation_lock(layout, uid) is not None
    path = tmp_path / "m" / "users" / uid / "memory" / ".consolidate-lock"
    assert path.is_file()
    rollback_consolidation_lock(layout, uid, 0)
    assert not path.exists()


def test_rollback_rewinds_mtime(tmp_path: Path) -> None:
    layout = ParaMemoryLayout(memory_root=tmp_path / "m")
    uid = "user1"
    path = tmp_path / "m" / "users" / uid / "memory" / ".consolidate-lock"
    target = 1_700_000_000.0
    _touch_lock(path, mtime_epoch_s=target, body="")
    try_acquire_consolidation_lock(layout, uid)
    rollback_consolidation_lock(layout, uid, int(target * 1000.0))
    st = path.stat()
    assert abs(st.st_mtime - target) < 1.0
