"""Tests for the MonitorsTool and monitors-check route."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ai.agent.progress import CollectingProgressSink
from ai.tools.types import ToolContext
from ai.tools.monitors import MonitorsTool, MONITORS_ROUTE

SAMPLE_MONITORS = """\
## NVDA Price Watch
- **Check**: Alert if NVDA drops below $120
- **Source**: price data
- **Priority**: high
- **Added**: 2026-05-02

## Fed Minutes
- **Check**: Flag if rate cut language appears
- **Source**: news/filings
- **Priority**: medium
- **Added**: 2026-05-01
"""


def _make_ctx(tmp_path: Path, bearer_token: str | None = None) -> ToolContext:
    return ToolContext(
        user_id="test-user",
        session_id="s1",
        session_permission="ReadWrite",
        channel="web",
        route="",
        progress=CollectingProgressSink(),
        bearer_token=bearer_token,
        memory_root=tmp_path,
        project_root=Path("."),
    )


def _monitors_path(tmp_path: Path) -> Path:
    return tmp_path / "users" / "test-user" / "life" / "monitors" / "MONITORS.md"


class TestMonitorsToolView:
    """Tests for the view action."""

    def test_view_no_file(self, tmp_path: Path) -> None:
        """View returns empty status when no MONITORS.md exists."""
        tool = MonitorsTool()
        ctx = _make_ctx(tmp_path)

        result = asyncio.run(tool._execute(ctx, {"action": "view"}))

        assert result.ok is True
        assert result.data["status"] == "empty"

    def test_view_with_content(self, tmp_path: Path) -> None:
        """View returns file contents when MONITORS.md exists."""
        tool = MonitorsTool()
        ctx = _make_ctx(tmp_path)
        path = _monitors_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(SAMPLE_MONITORS, "utf-8")

        result = asyncio.run(tool._execute(ctx, {"action": "view"}))

        assert result.ok is True
        assert result.data["status"] == "ok"
        assert "NVDA Price Watch" in result.data["content"]
        assert "Fed Minutes" in result.data["content"]


class TestMonitorsToolUpdate:
    """Tests for the update action."""

    def test_update_writes_file(self, tmp_path: Path) -> None:
        """Update creates MONITORS.md with the given content."""
        tool = MonitorsTool()
        ctx = _make_ctx(tmp_path)

        result = asyncio.run(tool._execute(ctx, {"action": "update", "content": SAMPLE_MONITORS}))

        assert result.ok is True
        assert result.data["items"] == 2
        assert _monitors_path(tmp_path).read_text("utf-8") == SAMPLE_MONITORS

    def test_update_missing_content(self, tmp_path: Path) -> None:
        """Update without content returns an error."""
        tool = MonitorsTool()
        ctx = _make_ctx(tmp_path)

        result = asyncio.run(tool._execute(ctx, {"action": "update"}))

        assert result.ok is False
        assert result.error["code"] == "missing_content"

    def test_update_empty_content_reports_cleared(self, tmp_path: Path) -> None:
        """Update with content that has no ## headings reports zero items."""
        tool = MonitorsTool()
        ctx = _make_ctx(tmp_path)

        result = asyncio.run(tool._execute(ctx, {"action": "update", "content": "nothing here\n"}))

        assert result.ok is True
        assert result.data["items"] == 0
        assert "Cleared" in result.data["message"]

    def test_unknown_action(self, tmp_path: Path) -> None:
        """Unknown action returns an error."""
        tool = MonitorsTool()
        ctx = _make_ctx(tmp_path)

        result = asyncio.run(tool._execute(ctx, {"action": "delete"}))

        assert result.ok is False
        assert result.error["code"] == "unknown_action"


class TestMonitorsToolScheduling:
    """Tests for automation scheduling integration."""

    @patch("ai.tools.monitors.find_automation_by_route", new_callable=AsyncMock)
    @patch("ai.tools.monitors.AutomationsClient")
    def test_update_creates_automation_when_none_exists(
        self,
        mock_client_cls: AsyncMock,
        mock_find: AsyncMock,
        tmp_path: Path,
    ) -> None:
        """Update with items creates a new automation if none exists."""
        mock_find.return_value = None
        mock_client = mock_client_cls.return_value
        mock_client.create_automation = AsyncMock(return_value={"automations_createAutomation": {"id": "a1"}})

        tool = MonitorsTool()
        ctx = _make_ctx(tmp_path, bearer_token="tok")

        result = asyncio.run(tool._execute(ctx, {"action": "update", "content": SAMPLE_MONITORS}))

        assert result.ok is True
        assert "created" in result.data["message"].lower()
        mock_client.create_automation.assert_called_once()
        call_kwargs = mock_client.create_automation.call_args.kwargs
        assert call_kwargs["route"] == MONITORS_ROUTE

    @patch("ai.tools.monitors.find_automation_by_route", new_callable=AsyncMock)
    @patch("ai.tools.monitors.AutomationsClient")
    def test_update_resumes_paused_automation(
        self,
        mock_client_cls: AsyncMock,
        mock_find: AsyncMock,
        tmp_path: Path,
    ) -> None:
        """Update with items resumes a paused automation."""
        mock_find.return_value = {"id": "a1", "status": "PAUSED", "route": MONITORS_ROUTE}
        mock_client = mock_client_cls.return_value
        mock_client.resume_automation = AsyncMock(return_value={"automations_resumeAutomation": {"id": "a1"}})

        tool = MonitorsTool()
        ctx = _make_ctx(tmp_path, bearer_token="tok")

        result = asyncio.run(tool._execute(ctx, {"action": "update", "content": SAMPLE_MONITORS}))

        assert result.ok is True
        assert "resumed" in result.data["message"].lower()
        mock_client.resume_automation.assert_called_once()

    @patch("ai.tools.monitors.find_automation_by_route", new_callable=AsyncMock)
    @patch("ai.tools.monitors.AutomationsClient")
    def test_update_pauses_automation_when_cleared(
        self,
        mock_client_cls: AsyncMock,
        mock_find: AsyncMock,
        tmp_path: Path,
    ) -> None:
        """Update with no items pauses an active automation."""
        mock_find.return_value = {"id": "a1", "status": "ACTIVE", "route": MONITORS_ROUTE}
        mock_client = mock_client_cls.return_value
        mock_client.pause_automation = AsyncMock(return_value={"automations_pauseAutomation": {"id": "a1"}})

        tool = MonitorsTool()
        ctx = _make_ctx(tmp_path, bearer_token="tok")

        result = asyncio.run(tool._execute(ctx, {"action": "update", "content": "empty\n"}))

        assert result.ok is True
        assert "paused" in result.data["message"].lower()
        mock_client.pause_automation.assert_called_once()

    def test_update_skips_scheduling_without_bearer(self, tmp_path: Path) -> None:
        """Update without bearer_token skips scheduling entirely."""
        tool = MonitorsTool()
        ctx = _make_ctx(tmp_path, bearer_token=None)

        result = asyncio.run(tool._execute(ctx, {"action": "update", "content": SAMPLE_MONITORS}))

        assert result.ok is True
        assert "Automation" not in result.data["message"]


class TestMonitorsCheckRoute:
    """Tests for the monitors-check route handler."""

    def test_route_no_file(self, tmp_path: Path) -> None:
        """Route returns early when no MONITORS.md exists."""
        from ai.memory.para import ParaMemoryLayout
        from ai.memory.writer import MemoryWriter
        from ai.routes.monitors_check import run

        layout = ParaMemoryLayout(tmp_path)
        layout.ensure_user_layout("test-user")
        writer = MemoryWriter(layout)

        from ai.routes.context import RouteContext
        from ai.schemas.agent import AgentChatRequest

        ctx = RouteContext(
            user_id="test-user",
            request=AgentChatRequest(request={"query": ""}, context={}),
            bearer_token=None,
            input={},
            layout=layout,
            writer=writer,
            progress=CollectingProgressSink(),
            call_llm=AsyncMock(return_value="No change."),
        )

        result = asyncio.run(run(ctx))
        assert result.metadata["items_checked"] == 0

    def test_route_processes_items(self, tmp_path: Path) -> None:
        """Route calls LLM for each item and logs flagged results."""
        from ai.memory.para import ParaMemoryLayout
        from ai.memory.writer import MemoryWriter
        from ai.routes.monitors_check import run

        layout = ParaMemoryLayout(tmp_path)
        layout.ensure_user_layout("test-user")
        writer = MemoryWriter(layout)

        monitors_dir = tmp_path / "users" / "test-user" / "life" / "monitors"
        monitors_dir.mkdir(parents=True, exist_ok=True)
        (monitors_dir / "MONITORS.md").write_text(SAMPLE_MONITORS, "utf-8")

        call_count = 0

        async def mock_llm(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            if "NVDA" in prompt:
                return "NVDA is at $115, below the $120 threshold."
            return "No change."

        from ai.routes.context import RouteContext
        from ai.schemas.agent import AgentChatRequest

        ctx = RouteContext(
            user_id="test-user",
            request=AgentChatRequest(request={"query": ""}, context={}),
            bearer_token=None,
            input={},
            layout=layout,
            writer=writer,
            progress=CollectingProgressSink(),
            call_llm=mock_llm,
        )

        result = asyncio.run(run(ctx))
        assert result.metadata["items_checked"] == 2
        assert result.metadata["items_flagged"] == 1
        assert call_count == 2
