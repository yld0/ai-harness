"""Tool catalog, OpenAPI-style definitions, and ToolRegistry wiring."""

from __future__ import annotations

from typing import Any

from ai.agent.loop import ToolRegistry
from ai.agent.prompt_builder import Channel
from ai.tools.user.ask_user import AskUserTool
from ai.tools._base import OpenAIFunctionDef, Tool
from ai.tools.financial.fmp import FmpGetQuote
from ai.tools.memory.grep import GrepTool
from ai.tools.monitors import MonitorsTool
from ai.tools.memory.memory_search import MemorySearchTool
from ai.tools.filesystem.permissions import SessionPermissionT, allows, parse_session
from ai.tools.filesystem.read_file import ReadFileTool
from ai.tools.types import ToolContext
from ai.tools.search.exa import ExaSearchTool
from ai.tools.search.perplexity import PerplexitySearchTool
from ai.tools.search.tavily import TavilySearchTool
from ai.tools.search.x_search import XSearchTool
from ai.tools.search.search_expert import SearchExpertToolStub
from ai.tools.improve.skill_stubs import AddSkillStub, PatchSkillStub
from ai.tools.internal.user_cli import UserCliTool
from ai.tools.web.web_fetch import WebFetchTool
from ai.tools.internal.yld import YldGraphqlQuery


def all_tools() -> tuple[Tool, ...]:
    """Return every tool instance known to the system."""
    return (
        FmpGetQuote(),
        YldGraphqlQuery(),
        MemorySearchTool(),
        ReadFileTool(),
        WebFetchTool(),
        GrepTool(),
        TavilySearchTool(),
        ExaSearchTool(),
        PerplexitySearchTool(),
        XSearchTool(),
        MonitorsTool(),
        AskUserTool(),
        SearchExpertToolStub(),
        UserCliTool(),
        AddSkillStub(),
        PatchSkillStub(),
    )


def _tool_visible_for_channel(tool: Tool, channel: Channel) -> bool:
    """Return whether the tool should be surfaced on the given channel."""
    if channel in tool.hidden_channels:
        return False
    return True


def _tool_visible_for_route(_tool: Tool, route: str) -> bool:  # noqa: ARG001
    """Reserved for future route profiles; all registered tools for Phase 6."""
    return True


def tool_allowed(
    tool: Tool,
    *,
    session: SessionPermissionT,
    channel: Channel,
    route: str,
) -> bool:
    """Check whether a tool passes permission, channel, and route gates."""
    if not allows(session, tool.required_permission):
        return False
    if not _tool_visible_for_channel(tool, channel):
        return False
    if not _tool_visible_for_route(tool, route):
        return False
    return True


def list_openai_tools(
    *,
    session: str | None,
    channel: Channel,
    route: str = "",
) -> list[OpenAIFunctionDef]:
    """Tools exposed to the provider for the given session, channel, and route."""
    perm = parse_session(session)
    out: list[OpenAIFunctionDef] = []
    for t in all_tools():
        if not tool_allowed(t, session=perm, channel=channel, route=route):
            continue
        out.append(t.openai_tool())
    return out


def register_tools(registry: ToolRegistry, *, include: set[str] | None = None) -> None:
    """Attach async handlers to the loop's ToolRegistry."""

    by_name: dict[str, Tool] = {t.name: t for t in all_tools()}

    for name, tool in by_name.items():
        if include is not None and name not in include:
            continue

        async def _bound(ctx: ToolContext, args: dict[str, Any], _ti: Tool = tool) -> str:
            return await _ti.run(ctx, args)

        registry.register(name, _bound)  # type: ignore[arg-type]
