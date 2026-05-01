"""Tests for the spaces_* bridge (GQL → knowledge-base.md)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from ai.memory.bridges.spaces import SpacesBridge, _write_knowledge_base
from ai.memory.para import ParaMemoryLayout


def _make_layout(tmp_path):
    return ParaMemoryLayout(tmp_path)


def _mock_spaces_data(spaces: list[dict]) -> dict:
    return {"spaces_spaces": {"spaces": spaces, "returnedCount": len(spaces)}}


@pytest.mark.asyncio
async def test_pull_writes_knowledge_base(tmp_path):
    bridge = SpacesBridge()
    layout = _make_layout(tmp_path)
    layout.ensure_user_layout("u1")

    data = _mock_spaces_data(
        [
            {
                "id": "sp1",
                "spaceID": "sp1",
                "title": "Tech Research",
                "description": "My tech space.",
                "instructions": "Focus on AI and semiconductors.",
            }
        ]
    )
    mock_client = AsyncMock()
    mock_client.execute.return_value = data

    result = await bridge.pull("u1", "tok", layout=layout, client=mock_client)

    assert result.ok is True
    assert result.records_written == 1

    kb_path = layout.entity_dir("u1", "spaces", "sp1") / "knowledge-base.md"
    assert kb_path.is_file()
    content = kb_path.read_text()
    assert "Tech Research" in content
    assert "AI and semiconductors" in content


@pytest.mark.asyncio
async def test_pull_multiple_spaces(tmp_path):
    bridge = SpacesBridge()
    layout = _make_layout(tmp_path)
    layout.ensure_user_layout("u1")

    data = _mock_spaces_data(
        [
            {
                "id": "sp1",
                "spaceID": "sp1",
                "title": "Space A",
                "instructions": "Focus A.",
            },
            {
                "id": "sp2",
                "spaceID": "sp2",
                "title": "Space B",
                "instructions": "Focus B.",
            },
        ]
    )
    mock_client = AsyncMock()
    mock_client.execute.return_value = data

    result = await bridge.pull("u1", "tok", layout=layout, client=mock_client)

    assert result.records_written == 2


@pytest.mark.asyncio
async def test_pull_empty_spaces(tmp_path):
    bridge = SpacesBridge()
    layout = _make_layout(tmp_path)
    mock_client = AsyncMock()
    mock_client.execute.return_value = _mock_spaces_data([])

    result = await bridge.pull("u1", "tok", layout=layout, client=mock_client)

    assert result.ok is True
    assert result.records_written == 0


@pytest.mark.asyncio
async def test_pull_network_error(tmp_path):
    bridge = SpacesBridge()
    layout = _make_layout(tmp_path)
    mock_client = AsyncMock()
    mock_client.execute.side_effect = RuntimeError("connection refused")

    result = await bridge.pull("u1", "tok", layout=layout, client=mock_client)

    assert result.ok is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_push_calls_update_mutation(tmp_path):
    bridge = SpacesBridge()
    layout = _make_layout(tmp_path)
    layout.ensure_user_layout("u1")

    space_dir = layout.entity_dir("u1", "spaces", "sp1")
    space_dir.mkdir(parents=True, exist_ok=True)
    kb_path = space_dir / "knowledge-base.md"
    kb_path.write_text("# Tech Research\n\nFocus on AI.")

    mock_client = AsyncMock()
    mock_client.execute.return_value = {"spaces_updateSpace": {"id": "sp1"}}

    result = await bridge.push(kb_path, "u1", "tok", layout=layout, client=mock_client)

    assert result.ok is True
    assert result.records_pushed == 1
    mock_client.execute.assert_called_once()


def test_write_knowledge_base_with_all_fields(tmp_path):
    path = tmp_path / "knowledge-base.md"
    space = {
        "title": "Finance",
        "description": "Finance space.",
        "instructions": "Focus on earnings.",
    }
    _write_knowledge_base(path, space)
    content = path.read_text()
    assert "# Finance" in content
    assert "Finance space." in content
    assert "Focus on earnings." in content


def test_write_knowledge_base_minimal(tmp_path):
    path = tmp_path / "knowledge-base.md"
    _write_knowledge_base(path, {"title": "Minimal"})
    assert "# Minimal" in path.read_text()
