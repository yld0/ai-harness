"""Conflict resolution tests — one case per bridge surface rule.

Bridge table:
  memories_*     → gql_wins (pull only)
  rules_*        → gql_wins (both)
  valuations_*   → last_write_wins (both)
  consensus_*    → gql_wins (pull only, stub)
  theses_*       → file_wins (both, stub)
  goals_*        → last_write_wins (both)
  spaces_*       → gql_wins (both)
  spaces_sources_* → gql_wins (both, stub)
  chats_*        → gql_wins (pull only, stub)
  watchlists_*   → gql_wins (both)
  alerts_*       → gql_wins (pull only)
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

import ai.memory.bridges.registry as bridges
from ai.memory.bridges.base import Bridge, NotImplementedBridge
from ai.memory.bridges.valuations import ValuationsBridge
from ai.memory.bridges.goals import GoalsBridge
from ai.memory.para import ParaMemoryLayout

# ─── Registry completeness ────────────────────────────────────────────────── #


def test_all_11_surfaces_registered():
    expected = {
        "memories",
        "rules",
        "valuations",
        "consensus",
        "theses",
        "goals",
        "spaces",
        "spaces_sources",
        "chats",
        "watchlists",
        "alerts",
    }
    registered = {b.gql_surface for b in bridges.all_bridges()}
    assert expected == registered, f"Missing: {expected - registered}"


def test_all_bridges_are_bridge_instances():
    for b in bridges.all_bridges():
        assert isinstance(b, Bridge)


def test_conflict_rules_match_spec():
    spec = {
        "memories": "gql_wins",
        "rules": "gql_wins",
        "valuations": "last_write_wins",
        "consensus": "gql_wins",
        "theses": "file_wins",
        "goals": "last_write_wins",
        "spaces": "gql_wins",
        "spaces_sources": "gql_wins",
        "chats": "gql_wins",
        "watchlists": "gql_wins",
        "alerts": "gql_wins",
    }
    for surface, expected_rule in spec.items():
        b = bridges.get_bridge(surface)
        assert b is not None, f"Bridge {surface!r} not registered"
        assert b.conflict_rule == expected_rule, f"{surface}: expected conflict_rule={expected_rule!r}, got {b.conflict_rule!r}"


def test_directions_match_spec():
    spec = {
        "memories": "pull",
        "rules": "both",
        "valuations": "both",
        "consensus": "pull",
        "theses": "both",
        "goals": "both",
        "spaces": "both",
        "spaces_sources": "both",
        "chats": "pull",
        "watchlists": "both",
        "alerts": "pull",
    }
    for surface, expected_dir in spec.items():
        b = bridges.get_bridge(surface)
        assert b is not None
        assert b.direction == expected_dir, f"{surface}: expected direction={expected_dir!r}, got {b.direction!r}"


# ─── gql_wins: push not meaningful (or stubbed) ──────────────────────────── #


@pytest.mark.asyncio
async def test_gql_wins_memories_pull_only_no_push(tmp_path):
    """memories_* is pull-only; push returns not_implemented."""
    b = bridges.get_bridge("memories")
    layout = ParaMemoryLayout(tmp_path)
    result = await b.push(tmp_path / "noop", "u1", "tok", layout=layout)
    # Default push from Bridge base returns not_implemented
    assert result.ok is False


@pytest.mark.asyncio
async def test_gql_wins_stub_pull_returns_not_implemented(tmp_path):
    """Stub bridges (consensus, chats, alerts…) return not_implemented on pull."""
    layout = ParaMemoryLayout(tmp_path)
    for surface in ("consensus", "chats", "spaces_sources"):
        b = bridges.get_bridge(surface)
        assert isinstance(b, NotImplementedBridge)
        result = await b.pull("u1", "tok", layout=layout)
        assert result.ok is False
        assert result.error == "not_implemented", f"{surface} expected not_implemented"


# ─── last_write_wins: valuations ─────────────────────────────────────────── #


def test_last_write_wins_valuations_remote_newer():
    local = {"updatedAt": "2026-04-01T00:00:00", "fair_value": 100}
    remote = {"updatedAt": "2026-04-26T00:00:00", "fair_value": 200}
    winner = ValuationsBridge.resolve_conflict(local, remote)
    assert winner["fair_value"] == 200


def test_last_write_wins_valuations_local_newer():
    local = {"updatedAt": "2026-04-26T00:00:00", "fair_value": 300}
    remote = {"updatedAt": "2026-04-01T00:00:00", "fair_value": 100}
    winner = ValuationsBridge.resolve_conflict(local, remote)
    assert winner["fair_value"] == 300


def test_last_write_wins_valuations_equal_timestamps_prefers_local():
    local = {"updatedAt": "2026-04-26T00:00:00", "fair_value": 111}
    remote = {"updatedAt": "2026-04-26T00:00:00", "fair_value": 222}
    winner = ValuationsBridge.resolve_conflict(local, remote)
    # When timestamps are equal, remote does NOT strictly beat local (>= condition)
    # Current impl: remote wins only when strictly greater; equal → local
    assert winner["fair_value"] == 111


# ─── last_write_wins: goals ───────────────────────────────────────────────── #


def test_last_write_wins_goals_remote_newer():
    local = {"updated_at": "2026-04-01", "status": "active"}
    remote = {"updated_at": "2026-04-26", "status": "completed"}
    winner = GoalsBridge.resolve_conflict(local, remote)
    assert winner["status"] == "completed"


def test_last_write_wins_goals_local_newer():
    local = {"updated_at": "2026-04-26", "status": "in_progress"}
    remote = {"updated_at": "2026-04-01", "status": "active"}
    winner = GoalsBridge.resolve_conflict(local, remote)
    assert winner["status"] == "in_progress"


# ─── file_wins: theses ────────────────────────────────────────────────────── #


@pytest.mark.asyncio
async def test_file_wins_theses_stub(tmp_path):
    """theses_* is file_wins but currently a stub; both ops return not_implemented."""
    b = bridges.get_bridge("theses")
    layout = ParaMemoryLayout(tmp_path)
    pull_r = await b.pull("u1", "tok", layout=layout)
    push_r = await b.push(tmp_path / "thesis.md", "u1", "tok", layout=layout)
    assert pull_r.ok is False
    assert push_r.ok is False


# ─── Offline / API-down behaviour ────────────────────────────────────────── #


@pytest.mark.asyncio
async def test_offline_mode_memories_no_crash(tmp_path):
    """MemoriesBridge fails gracefully when API is unreachable."""
    from ai.memory.bridges.memories import MemoriesBridge

    b = MemoriesBridge()
    layout = ParaMemoryLayout(tmp_path)
    mock_client = AsyncMock()
    mock_client.execute.side_effect = ConnectionError("unreachable")
    result = await b.pull("u1", "tok", layout=layout, client=mock_client)
    assert result.ok is False
    assert result.prompt_block == ""


@pytest.mark.asyncio
async def test_offline_mode_merge_falls_back_to_para(tmp_path):
    """merge_memory_with_graph returns PARA content unchanged on API failure."""
    from ai.memory.merge import merge_memory_with_graph
    from ai.memory.schemas import HotMemorySnapshot
    from ai.memory.para import ParaMemoryLayout

    para = HotMemorySnapshot(
        user_id="u1",
        session_id="s1",
        content="<memory-context>\nsome PARA content\n</memory-context>",
        metadata={},
    )
    mock_client = AsyncMock()
    mock_client.execute.side_effect = ConnectionError("unreachable")
    layout = ParaMemoryLayout(tmp_path)

    result = await merge_memory_with_graph(
        para_snapshot=para,
        layout=layout,
        user_id="u1",
        bearer_token="tok",
        client=mock_client,
    )

    assert "some PARA content" in result


# ─── Merge: prompt budget respected ──────────────────────────────────────── #


@pytest.mark.asyncio
async def test_merge_injects_graph_memories_block(tmp_path):
    from ai.memory.merge import merge_memory_with_graph, _inject_graph_block
    from ai.memory.schemas import HotMemorySnapshot
    from ai.memory.para import ParaMemoryLayout

    para_content = "<memory-context>\nPARA content\n</memory-context>"
    para = HotMemorySnapshot(user_id="u1", session_id="s1", content=para_content, metadata={})
    mock_memories_bridge = AsyncMock()
    mock_memories_bridge.pull = AsyncMock(
        return_value=__import__("ai.memory.bridges.base", fromlist=["PullResult"]).PullResult(
            ok=True, records_written=1, prompt_block="User is a financial analyst."
        )
    )

    layout = ParaMemoryLayout(tmp_path)
    result = await merge_memory_with_graph(
        para_snapshot=para,
        layout=layout,
        user_id="u1",
        bearer_token="tok",
        memories_bridge=mock_memories_bridge,
    )

    assert "Graph memories" in result
    assert "financial analyst" in result
    assert "PARA content" in result


def test_inject_graph_block_respects_budget():
    from ai.memory.merge import _inject_graph_block

    para = "<memory-context>\n" + "x" * 1000 + "\n</memory-context>"
    big_block = "y" * 500
    result = _inject_graph_block(para, big_block, budget_chars=1200)
    # Should truncate block because little budget remains
    assert len(result) <= 1200 + 100  # some overhead for tags


def test_inject_graph_block_no_budget_returns_unchanged():
    from ai.memory.merge import _inject_graph_block

    para = "x" * 25_000
    result = _inject_graph_block(para, "extra", budget_chars=25_000)
    # No room → unchanged
    assert result == para
