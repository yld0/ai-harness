"""Tool permission gating (ReadOnly vs WorkspaceWrite)."""

import asyncio
import json
from pathlib import Path

from ai.agent.progress import CollectingProgressSink
from ai.tools.context import ToolContext
from ai.tools.permissions import allows, PermissionMode
from ai.tools.skill_stubs import AddSkillStub
from ai.tools.user_cli import UserCliTool


def test_allows_matrix() -> None:
    assert allows("ReadOnly", PermissionMode.ReadOnly) is True
    assert allows("ReadOnly", PermissionMode.WorkspaceWrite) is False
    assert allows("ReadWrite", PermissionMode.WorkspaceWrite) is True
    assert allows("ReadWrite", PermissionMode.DangerFullAccess) is False


def test_user_cli_denied_readonly() -> None:
    sink = CollectingProgressSink()
    ctx = ToolContext(
        user_id="u1",
        session_id="s1",
        session_permission="ReadOnly",
        channel="web",
        route="",
        progress=sink,
        bearer_token="t",
        memory_root=Path("/tmp/memory"),
        project_root=Path("."),
    )
    tool = UserCliTool()

    async def run() -> str:
        return await tool.run(ctx, {"operation": "watchlists_list"})

    out = asyncio.run(run())
    body = json.loads(out)
    assert body["ok"] is False
    assert body["error"]["code"] == "permission_denied"


def test_add_skill_governance_stub() -> None:
    sink = CollectingProgressSink()
    ctx = ToolContext(
        user_id="u1",
        session_id="s1",
        session_permission="ReadWrite",
        channel="web",
        route="",
        progress=sink,
        bearer_token=None,
        memory_root=Path("/tmp/memory"),
        project_root=Path("."),
    )
    tool = AddSkillStub()

    async def run() -> str:
        return await tool.run(ctx, {"name": "x", "content": "y"})

    out = asyncio.run(run())
    body = json.loads(out)
    assert body["ok"] is False
    assert body["error"]["code"] == "governance_not_configured"
    assert "Phase 19" in body["error"]["hint"]
