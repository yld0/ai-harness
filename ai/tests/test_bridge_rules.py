"""Tests for the rules_* bridge (GQL → MEMORY.md rules section)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from ai.memory.bridges.rules import (
    RulesBridge,
    _format_rules_section,
    _parse_rules_from_section,
    _write_rules_section,
)
from ai.memory.para import ParaMemoryLayout
from ai.rules.models import Rule, RulesSnapshot


def _make_layout(tmp_path):
    return ParaMemoryLayout(tmp_path)


def _snapshot(
    always: list[tuple[str, str]] | None = None,
    manual: list[tuple[str, str]] | None = None,
) -> RulesSnapshot:
    aa = [Rule(id=str(i), name=n, instructions=ins, always_apply=True) for i, (n, ins) in enumerate(always or [])]
    ma = [Rule(id=str(i + 100), name=n, instructions=ins, always_apply=False) for i, (n, ins) in enumerate(manual or [])]
    return RulesSnapshot(always_apply=aa, manual=ma)


@pytest.mark.asyncio
async def test_pull_writes_rules_section_to_memory_md(tmp_path):
    bridge = RulesBridge()
    layout = _make_layout(tmp_path)
    layout.ensure_user_layout("u1")

    snap = _snapshot(always=[("Style", "Be concise.")], manual=[("Finance", "Use numbers.")])
    with patch("ai.memory.bridges.rules.fetch_rules_snapshot", new=AsyncMock(return_value=snap)):
        result = await bridge.pull("u1", "tok", layout=layout)

    assert result.ok is True
    assert result.records_written == 2

    memory_md = layout.guarded_user_path("u1", "MEMORY.md")
    assert memory_md.is_file()
    content = memory_md.read_text()
    assert "## Rules" in content
    assert "Style" in content
    assert "Finance" in content


@pytest.mark.asyncio
async def test_pull_no_rules_no_write(tmp_path):
    bridge = RulesBridge()
    layout = _make_layout(tmp_path)
    snap = RulesSnapshot()
    with patch("ai.memory.bridges.rules.fetch_rules_snapshot", new=AsyncMock(return_value=snap)):
        result = await bridge.pull("u1", "tok", layout=layout)

    assert result.ok is True
    assert result.records_written == 0


@pytest.mark.asyncio
async def test_pull_overwrites_existing_rules_section(tmp_path):
    bridge = RulesBridge()
    layout = _make_layout(tmp_path)
    layout.ensure_user_layout("u1")

    memory_md = layout.guarded_user_path("u1", "MEMORY.md")
    memory_md.write_text("## Rules (synced from GQL 2026-01-01T00:00:00Z)\n- **Old**: old rule.\n\n## Other section\nsome content\n")

    snap = _snapshot(always=[("NewRule", "New instructions.")])
    with patch("ai.memory.bridges.rules.fetch_rules_snapshot", new=AsyncMock(return_value=snap)):
        await bridge.pull("u1", "tok", layout=layout)

    content = memory_md.read_text()
    assert "NewRule" in content
    assert "Old" not in content
    assert "Other section" in content  # preserved


@pytest.mark.asyncio
async def test_pull_network_error_returns_not_ok(tmp_path):
    bridge = RulesBridge()
    layout = _make_layout(tmp_path)
    with patch(
        "ai.memory.bridges.rules.fetch_rules_snapshot",
        new=AsyncMock(side_effect=RuntimeError("timeout")),
    ):
        result = await bridge.pull("u1", "tok", layout=layout)

    assert result.ok is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_push_adds_local_rules_to_gql(tmp_path):
    bridge = RulesBridge()
    layout = _make_layout(tmp_path)
    layout.ensure_user_layout("u1")

    # Seed MEMORY.md with a rules section
    memory_md = layout.guarded_user_path("u1", "MEMORY.md")
    memory_md.write_text(
        "## Rules (synced from GQL 2026-01-01T00:00:00Z)\n\n" "### Always-apply\n- **Style**: Be concise.\n\n" "### Conditional\n- **Finance**: Use numbers.\n"
    )

    mock_client = AsyncMock()
    mock_client.execute.return_value = {"rules_addRule": {"id": "new1", "name": "Style"}}

    result = await bridge.push(memory_md, "u1", "tok", layout=layout, client=mock_client)

    assert result.ok is True
    assert result.records_pushed >= 1


# ─── Format helpers ───────────────────────────────────────────────────────── #


def test_format_rules_section_includes_always_apply():
    snap = _snapshot(always=[("A", "Rule A body.")])
    section = _format_rules_section(snap)
    assert "Always-apply" in section
    assert "Rule A body." in section


def test_parse_rules_from_section_roundtrip():
    snap = _snapshot(always=[("Style", "Be concise.")], manual=[("Finance", "Use numbers.")])
    section = _format_rules_section(snap)
    rules = _parse_rules_from_section("## Intro\n\n" + section)
    names = [r[0] for r in rules]
    assert "Style" in names
    assert "Finance" in names
    # Always-apply flag
    assert any(r[0] == "Style" and r[2] is True for r in rules)
    assert any(r[0] == "Finance" and r[2] is False for r in rules)
