"""Tests for memory automation route handlers: decay-tick, weekly-synthesis, heartbeat-extract."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml

from ai.memory.para import ParaMemoryLayout
from ai.memory.schemas import FactStatus, MemoryFact, Validity
from ai.memory.writer import MemoryWriter
from ai.routes.context import RouteContext, RouteResult

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_ctx(tmp_path: Path, input_data: dict | None = None) -> RouteContext:
    layout = ParaMemoryLayout(tmp_path)
    layout.ensure_user_layout("u1")
    return RouteContext(
        user_id="u1",
        request=None,  # type: ignore[arg-type]
        bearer_token=None,
        input=input_data or {},
        layout=layout,
        writer=MemoryWriter(layout),
        progress=AsyncMock(),
        call_llm=AsyncMock(return_value="Extracted: nothing notable."),
    )


def _make_fact(
    fid: str,
    *,
    validity: Validity = Validity.POINT_IN_TIME,
    status: FactStatus = FactStatus.ACTIVE,
    days_old: int = 0,
    expires: date | None = None,
) -> MemoryFact:
    recorded = date(2026, 1, 1) if days_old else date.today()
    return MemoryFact(
        id=fid,
        fact=f"fact-{fid}",
        validity=validity,
        status=status,
        recorded_at=recorded,
        expires=expires,
    )


def _write_items(path: Path, facts: list[MemoryFact]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [f.model_dump(mode="json", exclude_none=True) for f in facts]
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


# ─── memory-decay-tick ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_decay_tick_no_life_dir(tmp_path):
    from ai.routes.memory_decay_tick import run

    ctx = _make_ctx(tmp_path)
    # Remove life dir to simulate empty user
    import shutil

    life_dir = tmp_path / "users" / "u1" / "life"
    if life_dir.exists():
        shutil.rmtree(life_dir)
    result = await run(ctx)
    assert result.ok is True
    assert result.metadata["files_updated"] == 0


@pytest.mark.asyncio
async def test_decay_tick_transitions_expired_fact(tmp_path):
    from ai.routes.memory_decay_tick import run

    ctx = _make_ctx(tmp_path, {"date": "2026-06-01"})

    fact = _make_fact("f1", validity=Validity.EXPIRES, expires=date(2026, 1, 1))
    items_path = tmp_path / "users" / "u1" / "life" / "tickers" / "AAPL" / "items.yaml"
    _write_items(items_path, [fact])

    result = await run(ctx)
    assert result.ok is True
    assert result.metadata["facts_transitioned"] == 1

    updated = yaml.safe_load(items_path.read_text())
    assert updated[0]["status"] == "historical"


@pytest.mark.asyncio
async def test_decay_tick_no_change_when_all_current(tmp_path):
    from ai.routes.memory_decay_tick import run

    ctx = _make_ctx(tmp_path, {"date": date.today().isoformat()})

    fact = _make_fact("f1", validity=Validity.EVERGREEN)
    items_path = tmp_path / "users" / "u1" / "life" / "tickers" / "MSFT" / "items.yaml"
    _write_items(items_path, [fact])

    result = await run(ctx)
    assert result.ok is True
    # Evergreen facts do not change status
    assert result.metadata["facts_transitioned"] == 0


@pytest.mark.asyncio
async def test_decay_tick_returns_summary_text(tmp_path):
    from ai.routes.memory_decay_tick import run

    ctx = _make_ctx(tmp_path)
    result = await run(ctx)
    assert "Decay tick" in result.text


# ─── memory-weekly-synthesis ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_weekly_synthesis_empty_user(tmp_path):
    from ai.routes.memory_weekly_synthesis import run

    ctx = _make_ctx(tmp_path)
    result = await run(ctx)
    assert result.ok is True
    assert result.metadata["entities_processed"] == 0


@pytest.mark.asyncio
async def test_weekly_synthesis_creates_summary_md(tmp_path):
    from ai.routes.memory_weekly_synthesis import run

    ctx = _make_ctx(tmp_path)

    # Seed one ticker entity
    writer = ctx.writer
    fact = _make_fact("f1", validity=Validity.EVERGREEN)
    writer.write_fact("u1", kind="tickers", entity_id="AAPL", fact=fact)

    result = await run(ctx)
    assert result.ok is True
    assert result.metadata["entities_processed"] >= 1
    summary_path = tmp_path / "users" / "u1" / "life" / "tickers" / "AAPL" / "summary.md"
    assert summary_path.is_file()
    assert "AAPL" in summary_path.read_text()


@pytest.mark.asyncio
async def test_weekly_synthesis_multiple_kinds(tmp_path):
    from ai.routes.memory_weekly_synthesis import run

    ctx = _make_ctx(tmp_path)

    writer = ctx.writer
    for kind, eid in [("tickers", "TSLA"), ("sectors", "tech"), ("people", "alice")]:
        fact = _make_fact("f1", validity=Validity.EVERGREEN)
        writer.write_fact("u1", kind=kind, entity_id=eid, fact=fact)

    result = await run(ctx)
    assert result.metadata["entities_processed"] >= 3


# ─── heartbeat-extract ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_heartbeat_extract_empty_user(tmp_path):
    from ai.routes.heartbeat_extract import run

    ctx = _make_ctx(tmp_path)
    result = await run(ctx)
    assert result.ok is True
    assert result.metadata["entities_processed"] == 0


@pytest.mark.asyncio
async def test_heartbeat_extract_calls_llm_per_entity(tmp_path):
    from ai.routes.heartbeat_extract import run

    call_llm = AsyncMock(return_value="New insight: price went up.")
    ctx = _make_ctx(tmp_path)
    ctx = RouteContext(
        user_id="u1",
        request=None,  # type: ignore[arg-type]
        bearer_token=None,
        input={},
        layout=ctx.layout,
        writer=ctx.writer,
        progress=AsyncMock(),
        call_llm=call_llm,
    )

    writer = ctx.writer
    fact = _make_fact("f1", validity=Validity.EVERGREEN)
    writer.write_fact("u1", kind="tickers", entity_id="NVDA", fact=fact)

    result = await run(ctx)
    assert result.ok is True
    assert result.metadata["entities_processed"] >= 1
    call_llm.assert_awaited()


@pytest.mark.asyncio
async def test_heartbeat_extract_skips_no_new_facts(tmp_path):
    from ai.routes.heartbeat_extract import run

    call_llm = AsyncMock(return_value="No new facts.")
    ctx = RouteContext(
        user_id="u1",
        request=None,  # type: ignore[arg-type]
        bearer_token=None,
        input={},
        layout=ParaMemoryLayout(tmp_path),
        writer=MemoryWriter(ParaMemoryLayout(tmp_path)),
        progress=AsyncMock(),
        call_llm=call_llm,
    )

    writer = ctx.writer
    fact = _make_fact("f1", validity=Validity.EVERGREEN)
    writer.write_fact("u1", kind="tickers", entity_id="AMD", fact=fact)

    result = await run(ctx)
    # No daily note written, but no error
    assert result.ok is True
    daily_notes = list((tmp_path / "users" / "u1" / "memory").glob("*.md") if (tmp_path / "users" / "u1" / "memory").exists() else [])
    assert len(daily_notes) == 0


@pytest.mark.asyncio
async def test_heartbeat_extract_kind_filter(tmp_path):
    from ai.routes.heartbeat_extract import run

    call_llm = AsyncMock(return_value="Insight: macro is shifting.")
    layout = ParaMemoryLayout(tmp_path)
    writer = MemoryWriter(layout)
    layout.ensure_user_layout("u1")

    fact = _make_fact("f1", validity=Validity.EVERGREEN)
    writer.write_fact("u1", kind="tickers", entity_id="SPY", fact=fact)
    writer.write_fact("u1", kind="macros", entity_id="inflation", fact=fact)

    ctx = RouteContext(
        user_id="u1",
        request=None,  # type: ignore[arg-type]
        bearer_token=None,
        input={"kind": "macros"},
        layout=layout,
        writer=writer,
        progress=AsyncMock(),
        call_llm=call_llm,
    )
    result = await run(ctx)
    assert result.ok is True
    # Only the macro entity should be processed
    assert result.metadata["entities_processed"] == 1
