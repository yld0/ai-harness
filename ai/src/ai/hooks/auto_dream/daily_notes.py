"""Count daily-note files (``memory/YYYY-MM-DD.md``) for auto-dream session proxy gate."""

from __future__ import annotations

import re

from ai.memory.para import ParaMemoryLayout
from ai.hooks.auto_dream.consolidation_lock import LOCK_NAME

DAY_STEM_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def count_daily_notes_touched_since(
    layout: ParaMemoryLayout,
    user_id: str,
    *,
    since_ms: float,
    exclude_day: str,
) -> int:
    """
    Count ``memory/*.md`` daily note files modified after *since_ms* (mtime ms), excluding *exclude_day* stem.

    The consolidation lock file and non-daily markdown files under ``memory/`` are ignored.
    """
    mem = layout.guarded_user_path(user_id, "memory")
    if not mem.is_dir():
        return 0
    count = 0
    for path in mem.iterdir():
        if path.name == LOCK_NAME:
            continue
        if not path.is_file():
            continue
        if path.suffix != ".md":
            continue
        stem = path.stem
        if stem == exclude_day or not DAY_STEM_PATTERN.fullmatch(stem):
            continue
        mtime_ms = path.stat().st_mtime * 1000.0
        if mtime_ms > since_ms:
            count += 1
    return count
