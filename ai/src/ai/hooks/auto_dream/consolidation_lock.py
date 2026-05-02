"""Cross-process consolidation lock: mtime of ``.consolidate-lock`` encodes last consolidated time."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from ai.memory.para import ParaMemoryLayout

logger = logging.getLogger(__name__)

LOCK_NAME = ".consolidate-lock"
# Stale past this even if the PID is live (PID reuse guard).
HOLDER_STALE_MS = 60 * 60 * 1000


def consolidation_lock_path(layout: ParaMemoryLayout, user_id: str) -> Path:
    """Return the path to the lock file under ``users/<id>/memory``."""
    return layout.guarded_user_path(user_id, "memory", LOCK_NAME)


def read_last_consolidated_at_ms(layout: ParaMemoryLayout, user_id: str) -> float:
    """
    Return ``mtime`` of the lock file in milliseconds, or ``0.0`` if absent.

    Raises:
        MemoryPathError: If the resolved path escapes the user memory root.
    """
    path = consolidation_lock_path(layout, user_id)
    try:
        return path.stat().st_mtime * 1000.0
    except FileNotFoundError:
        return 0.0


def _holder_pid(body: str) -> int | None:
    raw = body.strip()
    if not raw:
        return None
    try:
        pid = int(raw, 10)
    except ValueError:
        return None
    if pid <= 0:
        return None
    return pid


def _is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def try_acquire_consolidation_lock(layout: ParaMemoryLayout, user_id: str) -> int | None:
    """
    Write the current process id to the lock file (``mtime`` becomes now).

    Returns:
        Prior ``mtime`` in milliseconds before acquire, on success.
        ``None`` if another live holder holds a non-stale lock, or verify lost a race.
    """
    path = consolidation_lock_path(layout, user_id)

    mtime_ms: float | None = None
    holder_pid: int | None = None
    try:
        st = path.stat()
        mtime_ms = st.st_mtime * 1000.0
        holder_pid = _holder_pid(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.debug("consolidation lock read failed: %s", exc)
        mtime_ms = None

    current_time_ms = time.time() * 1000.0

    if mtime_ms is not None and current_time_ms - mtime_ms < HOLDER_STALE_MS:
        if holder_pid is not None and _is_pid_running(holder_pid):
            logger.debug(
                "consolidation lock held by live PID %s",
                holder_pid,
            )
            return None

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()), encoding="utf-8")

    try:
        verify = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if _holder_pid(verify) != os.getpid():
        return None

    prior = int(mtime_ms) if mtime_ms is not None else 0
    return prior


def rollback_consolidation_lock(layout: ParaMemoryLayout, user_id: str, prior_mtime_ms: int) -> None:
    """
    Rewind lock ``mtime`` to *prior_mtime_ms*, or remove the file if *prior_mtime_ms* is 0.

    Clears the PID body before ``utime`` so this process is not mistaken for the holder.
    """
    path = consolidation_lock_path(layout, user_id)
    try:
        if prior_mtime_ms == 0:
            path.unlink(missing_ok=True)
            return
        path.write_text("", encoding="utf-8")
        t_sec = prior_mtime_ms / 1000.0
        os.utime(path, (t_sec, t_sec))
    except OSError as exc:
        logger.warning("consolidation lock rollback failed: %s", exc)
