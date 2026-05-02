"""Tests for extract_memories hook (daily notes + ticker extract)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

from ai.config import hook_config
from ai.hooks.extract_memories import ExtractMemoriesHook
from ai.hooks.types import HookContext
from ai.memory.para import ParaMemoryLayout
from ai.memory.writer import MemoryWriter


def _ctx(uid: str, turn: int, msg: str, cfg) -> HookContext:
    return HookContext(
        user_id=uid,
        conversation_id="c1",
        user_message=msg,
        response_text="ok",
        request=MagicMock(),
        messages=[],
        config=cfg,
        turn_index=turn,
    )


def test_extract_skipped_turn_zero(tmp_path: Path) -> None:
    layout = ParaMemoryLayout(memory_root=tmp_path / "m")
    cfg = replace(hook_config, AI_EXTRACT_MEMORIES_EVERY_N=1)
    w = MemoryWriter(layout)
    hook = ExtractMemoriesHook(writer=w)
    r = hook.run(_ctx("u1", 0, "hello", cfg))
    assert r.detail == "skipped_cadence"


def test_extract_skipped_cadence(tmp_path: Path) -> None:
    layout = ParaMemoryLayout(memory_root=tmp_path / "m")
    cfg = replace(hook_config, AI_EXTRACT_MEMORIES_EVERY_N=5)
    hook = ExtractMemoriesHook(MemoryWriter(layout))
    r = hook.run(_ctx("u1", 1, "Ping AAPL ticker", cfg))
    assert r.detail == "skipped_cadence"


def test_extract_writes_daily_note(tmp_path: Path) -> None:
    layout = ParaMemoryLayout(memory_root=tmp_path / "m")
    cfg = replace(hook_config, AI_EXTRACT_MEMORIES_EVERY_N=2)
    hook = ExtractMemoriesHook(MemoryWriter(layout))
    r = hook.run(_ctx("u2", 2, "Discuss AAPL fundamentals", cfg))
    assert r.ok
    dn = layout.daily_note_path("u2", date.today().isoformat())
    text = dn.read_text(encoding="utf-8")
    assert "Discuss AAPL" in text
