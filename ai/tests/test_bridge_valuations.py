"""Tests for the valuations_* bridge (file-side operations + conflict resolution)."""

from __future__ import annotations

import pytest

from ai.memory.bridges.valuations import ValuationsBridge
from ai.memory.para import ParaMemoryLayout


def _make_layout(tmp_path):
    return ParaMemoryLayout(tmp_path)


@pytest.mark.asyncio
async def test_pull_returns_not_implemented(tmp_path):
    bridge = ValuationsBridge()
    layout = _make_layout(tmp_path)
    result = await bridge.pull("u1", "tok", layout=layout)
    assert result.ok is False
    assert result.error == "not_implemented"


@pytest.mark.asyncio
async def test_push_returns_not_implemented(tmp_path):
    bridge = ValuationsBridge()
    layout = _make_layout(tmp_path)
    result = await bridge.push(tmp_path / "noop.yaml", "u1", "tok", layout=layout)
    assert result.ok is False
    assert result.error == "not_implemented"


def test_write_and_read_valuation(tmp_path):
    layout = _make_layout(tmp_path)
    layout.ensure_user_layout("u1")
    ticker_dir = layout.entity_dir("u1", "tickers", "AAPL")
    ticker_dir.mkdir(parents=True, exist_ok=True)
    val_path = ticker_dir / "valuation.yaml"

    data = {"model": "DCF", "fair_value": 180.0, "upside": "15%"}
    ValuationsBridge.write_valuation(val_path, data, updated_at="2026-04-26T10:00:00Z")

    loaded = ValuationsBridge.read_valuation(val_path)
    assert loaded["model"] == "DCF"
    assert loaded["fair_value"] == 180.0
    assert loaded["updatedAt"] == "2026-04-26T10:00:00Z"


def test_write_valuation_injects_updated_at(tmp_path):
    val_path = tmp_path / "valuation.yaml"
    ValuationsBridge.write_valuation(val_path, {"model": "ComparableComp"})
    loaded = ValuationsBridge.read_valuation(val_path)
    assert "updatedAt" in loaded


def test_read_missing_file_returns_empty(tmp_path):
    result = ValuationsBridge.read_valuation(tmp_path / "missing.yaml")
    assert result == {}


def test_resolve_conflict_remote_wins_if_newer():
    local = {"updatedAt": "2026-04-01", "fair_value": 100}
    remote = {"updatedAt": "2026-04-26", "fair_value": 150}
    winner = ValuationsBridge.resolve_conflict(local, remote)
    assert winner["fair_value"] == 150


def test_resolve_conflict_local_wins_if_newer():
    local = {"updatedAt": "2026-04-26", "fair_value": 200}
    remote = {"updatedAt": "2026-04-01", "fair_value": 100}
    winner = ValuationsBridge.resolve_conflict(local, remote)
    assert winner["fair_value"] == 200


def test_resolve_conflict_empty_remote_ts_local_wins():
    local = {"updatedAt": "2026-04-26", "fair_value": 200}
    remote = {"fair_value": 100}  # no timestamp
    winner = ValuationsBridge.resolve_conflict(local, remote)
    assert winner["fair_value"] == 200
