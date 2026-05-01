"""Tool registry listing, execution, CoT events, and mocked search calls."""

import asyncio
import json
from pathlib import Path
import httpx

from ai.agent.loop import ToolCall, ToolRegistry

# Snapshot before any test patches `httpx.AsyncClient` on a submodule.
_REAL_ASYNC_CLIENT = httpx.AsyncClient


# httpx may pass `transport=...` internally; we replace with a mock transport.
def _async_client_with_transport(tr: httpx.MockTransport, *args: object, **kwargs: object) -> httpx.AsyncClient:
    merged = dict(kwargs)
    merged.pop("transport", None)
    return _REAL_ASYNC_CLIENT(*args, transport=tr, **merged)


from ai.agent.progress import CollectingProgressSink
from ai.tools.context import ToolContext, set_tool_context, reset_tool_context
from ai.tools.registry import all_tools, list_openai_tools, register_tools
from ai.tools.search.tavily import TavilySearchTool


def test_list_openai_tools_readonly_excludes_workspace_writes() -> None:
    names = {t["function"]["name"] for t in list_openai_tools(session="ReadOnly", channel="web")}
    assert "user_cli" not in names
    assert "add_skill" not in names
    assert "memory_search" in names


def test_list_openai_tools_readwrite_includes_user_cli() -> None:
    names = {t["function"]["name"] for t in list_openai_tools(session="ReadWrite", channel="web")}
    assert "user_cli" in names
    assert "add_skill" in names


def test_read_file_hidden_on_whatsapp() -> None:
    names = {t["function"]["name"] for t in list_openai_tools(session="ReadWrite", channel="whatsapp")}
    assert "read_file" not in names


def test_registry_registers_all_tools() -> None:
    reg = ToolRegistry()
    register_tools(reg)
    for t in all_tools():
        assert reg.has_tool(t.name)


def test_tool_emits_tool_start_and_tool_done() -> None:
    from ai.tools.heartbeat import HeartbeatTool

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
    tool = HeartbeatTool()

    async def run() -> None:
        await tool.run(ctx, {"label": "ping", "wait_s": 0})

    asyncio.run(run())
    cot = [ev["payload"] for ev in sink.events if ev.get("type") == "cot_step"]
    types = [p.get("step_type") for p in cot]
    assert "tool_start" in types
    assert "tool_done" in types


def test_tool_registry_executes_with_context(monkeypatch, tmp_path: Path) -> None:
    reg = ToolRegistry()
    register_tools(reg)
    sink = CollectingProgressSink()
    ctx = ToolContext(
        user_id="u1",
        session_id="s1",
        session_permission="ReadWrite",
        channel="web",
        route="",
        progress=sink,
        bearer_token=None,
        memory_root=tmp_path,
        project_root=tmp_path,
    )
    token = set_tool_context(ctx)
    try:
        monkeypatch.setenv("FMP_API_KEY", "fake")
        import ai.tools.fmp as fmp_mod

        transport = httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                json=[{"symbol": "MSFT", "price": 100}],
            )
        )
        monkeypatch.setattr(
            fmp_mod.httpx,
            "AsyncClient",
            lambda *a, **kw: _async_client_with_transport(transport, *a, **kw),
        )

        async def go() -> str:
            return await reg.execute(ToolCall(id="1", name="fmp_get_quote", arguments={"symbol": "MSFT"}))

        raw = asyncio.run(go())
        data = json.loads(raw)
        assert data["ok"] is True
        assert data["data"]["symbol"] == "MSFT"
    finally:
        reset_tool_context(token)


def test_tavily_mocked_no_network(monkeypatch) -> None:
    import ai.tools.search.tavily as tav

    monkeypatch.setenv("TAVILY_API_KEY", "k")
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"results": [{"url": "https://example.com"}]}))
    monkeypatch.setattr(
        tav.httpx,
        "AsyncClient",
        lambda *a, **kw: _async_client_with_transport(transport, *a, **kw),
    )
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
    tool = TavilySearchTool()

    async def run() -> str:
        return await tool.run(ctx, {"query": "MSFT earnings"})

    out = asyncio.run(run())
    body = json.loads(out)
    assert body["ok"] is True
    assert body["data"]["results"]


def test_exa_mocked(monkeypatch) -> None:
    from ai.tools.search.exa import ExaSearchTool

    import ai.tools.search.exa as exa_mod

    monkeypatch.setenv("EXA_API_KEY", "k")
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"results": []}))
    monkeypatch.setattr(
        exa_mod.httpx,
        "AsyncClient",
        lambda *a, **kw: _async_client_with_transport(transport, *a, **kw),
    )
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
    tool = ExaSearchTool()

    async def run() -> str:
        return await tool.run(ctx, {"query": "NVDA"})

    out = asyncio.run(run())
    assert json.loads(out)["ok"] is True


def test_perplexity_mocked(monkeypatch) -> None:
    from ai.tools.search.perplexity import PerplexitySearchTool

    import ai.tools.search.perplexity as ppl_mod

    monkeypatch.setenv("PERPLEXITY_API_KEY", "k")
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}))
    monkeypatch.setattr(
        ppl_mod.httpx,
        "AsyncClient",
        lambda *a, **kw: _async_client_with_transport(transport, *a, **kw),
    )
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
    tool = PerplexitySearchTool()

    async def run() -> str:
        return await tool.run(ctx, {"query": "test"})

    assert json.loads(asyncio.run(run()))["ok"] is True


def test_x_search_mocked(monkeypatch) -> None:
    from ai.tools.search.x_search import XSearchTool

    import ai.tools.search.x_search as xmod

    monkeypatch.setenv("X_BEARER_TOKEN", "t")
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"data": []}))
    monkeypatch.setattr(
        xmod.httpx,
        "AsyncClient",
        lambda *a, **kw: _async_client_with_transport(transport, *a, **kw),
    )
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
    tool = XSearchTool()

    async def run() -> str:
        return await tool.run(ctx, {"query": "tsla"})

    assert json.loads(asyncio.run(run()))["ok"] is True
