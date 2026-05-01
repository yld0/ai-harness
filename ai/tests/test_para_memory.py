from datetime import date

import pytest

from ai.memory.loader import MemoryLoader
from ai.memory.para import MemoryPathError, ParaMemoryLayout
from ai.memory.schemas import MemoryFact, Validity
from ai.memory.search import MemorySearch
from ai.memory.writer import MemoryWriter


def fact(fact_id: str = "MSFT-1", text: str = "MSFT Azure growth accelerated") -> MemoryFact:
    return MemoryFact(
        id=fact_id,
        fact=text,
        category="earnings",
        validity=Validity.EVERGREEN,
        recorded_at=date(2026, 4, 26),
        related_entities=["tickers/MSFT"],
    )


def test_path_jail_blocks_escape(tmp_path) -> None:
    layout = ParaMemoryLayout(tmp_path)
    with pytest.raises(MemoryPathError):
        layout.guarded_user_path("user-1", "..", "global", "facts.yaml")
    with pytest.raises(MemoryPathError):
        layout.entity_dir("user-1", "tickers", "../MSFT")


def test_writer_creates_ticker_and_space_layouts_and_facts(tmp_path) -> None:
    writer = MemoryWriter(ParaMemoryLayout(tmp_path))

    ticker_items = writer.write_fact("user-1", kind="tickers", entity_id="MSFT", fact=fact())
    space_dir = writer.ensure_entity_layout("user-1", kind="spaces", entity_id="space-1")

    assert ticker_items.name == "items.yaml"
    assert (ticker_items.parent / "summary.md").exists()
    assert (ticker_items.parent / "thesis.md").exists()
    assert (ticker_items.parent / "valuation.yaml").exists()
    assert (ticker_items.parent / "consensus.yaml").exists()
    assert (space_dir / "sources.yaml").exists()
    assert (space_dir / "knowledge-base.md").exists()
    assert MemoryWriter.read_facts_path(ticker_items)[0].id == "MSFT-1"


def test_daily_note_append(tmp_path) -> None:
    writer = MemoryWriter(ParaMemoryLayout(tmp_path))
    path = writer.append_daily_note(
        "user-1",
        "Discussed MSFT valuation",
        day=date(2026, 4, 26),
    )

    assert path.name == "2026-04-26.md"
    assert "Discussed MSFT valuation" in path.read_text(encoding="utf-8")


def test_hot_snapshot_loads_user_memory_and_mentioned_entity_then_freezes(
    tmp_path,
) -> None:
    layout = ParaMemoryLayout(tmp_path)
    writer = MemoryWriter(layout)
    root = layout.ensure_user_layout("user-1")
    (root / "USER.md").write_text("Prefers concise answers", encoding="utf-8")
    (root / "MEMORY.md").write_text("Uses DCF checks", encoding="utf-8")
    entity_dir = writer.ensure_entity_layout("user-1", kind="tickers", entity_id="MSFT")
    (entity_dir / "summary.md").write_text("MSFT summary hot fact", encoding="utf-8")

    loader = MemoryLoader(layout)
    first = loader.load_hot_snapshot(
        user_id="user-1",
        session_id="conversation-1",
        first_message="Tell me about MSFT",
    )
    (root / "MEMORY.md").write_text("Updated after first load", encoding="utf-8")
    frozen = loader.load_hot_snapshot(
        user_id="user-1",
        session_id="conversation-1",
        first_message="Tell me about MSFT",
    )
    rebuilt = loader.load_hot_snapshot(
        user_id="user-1",
        session_id="conversation-1",
        first_message="Tell me about MSFT",
        rebuild=True,
    )

    assert "Prefers concise answers" in first.content
    assert "Uses DCF checks" in first.content
    assert "MSFT summary hot fact" in first.content
    assert frozen.content == first.content
    assert "Updated after first load" in rebuilt.content


def test_memory_search_local_finds_yaml_and_markdown(tmp_path) -> None:
    layout = ParaMemoryLayout(tmp_path)
    writer = MemoryWriter(layout)
    writer.write_fact(
        "user-1",
        kind="tickers",
        entity_id="MSFT",
        fact=fact(text="MSFT has Copilot tailwinds"),
    )
    writer.append_daily_note("user-1", "Talked about Copilot revenue", day=date(2026, 4, 26))

    results = MemorySearch(layout).local_search("user-1", "Copilot")

    assert results
    assert results[0].score >= 1
    assert "Copilot" in results[0].snippet
