"""Tests for DreamRunner parse and writes."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai.memory.para import ParaMemoryLayout
from ai.memory.writer import MemoryWriter
from ai.hooks.auto_dream.dream_runner import DreamRunner


@pytest.mark.asyncio
async def test_dream_writes_memory_and_entity(tmp_path: Path) -> None:
    root = tmp_path / "m"
    layout = ParaMemoryLayout(memory_root=root)
    uid = "u1"
    layout.ensure_user_layout(uid)
    MemoryWriter(layout).ensure_entity_layout(uid, kind="tickers", entity_id="ABCD")
    mi_path = layout.guarded_user_path(uid, "MEMORY.md")
    mi_path.write_text("# Old index\n", encoding="utf-8")
    summary_path = layout.guarded_user_path(uid, "life", "tickers", "ABCD", "summary.md")
    summary_path.write_text("# ABCD\n", encoding="utf-8")

    async def fake_llm(prompt: str) -> str:
        assert "Dream" in prompt or "MEMORY" in prompt
        return "<<MEMORY_INDEX>>\n## Index line\n<<END>>\n<<ENTITY tickers ABCD>>\n## Consolidated ticker\nyes\n<<END>>\n"

    dr = DreamRunner(layout=layout, call_llm=fake_llm)
    res = await dr.run(uid, recent_daily_notes=3)
    assert res.ok
    assert "## Index line" in mi_path.read_text(encoding="utf-8")
    tx = summary_path.read_text(encoding="utf-8")
    assert "Consolidated ticker" in tx


@pytest.mark.asyncio
async def test_dream_parse_failure(tmp_path: Path) -> None:
    layout = ParaMemoryLayout(memory_root=tmp_path / "m")
    uid = "u1"
    layout.ensure_user_layout(uid)

    async def bad_llm(_: str) -> str:
        return "no markers here"

    dr = DreamRunner(layout=layout, call_llm=bad_llm)
    res = await dr.run(uid, recent_daily_notes=1)
    assert not res.ok
    assert res.skipped_parse
