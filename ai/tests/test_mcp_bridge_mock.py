"""Tests for Phase 20: MCP client bridge (all HTTP calls mocked — no mcp SDK required).

The real mcp SDK is not installed in CI.  All tests use injected fake clients
and configs so the SDK import path is never exercised here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from shared.envutil.config import load

import ai.mcp.config as ai_mcp_config_mod
from ai.config import MCPConfig as MCPEnvConfig
from ai.mcp.config import (
    MCPConfig,
    MCPServerConfig,
    load_mcp_config,
    parse_mcp_servers_env,
)
from ai.mcp.client import MCPToolDef, _extract_content
from ai.tools.mcp_bridge import (
    MCPToolBridge,
    load_mcp_tools,
    mcp_tool_name,
)
from ai.tools.types import ToolContext
from ai.tools.permissions import PermissionMode
from ai.agent.progress import NoopProgressSink

# ─── helpers ──────────────────────────────────────────────────────────────────


def _tool_def(name: str = "get_quote", server: str = "fmp") -> MCPToolDef:
    return MCPToolDef(
        name=name,
        description=f"Fetch {name} data",
        input_schema={"type": "object", "properties": {"ticker": {"type": "string"}}},
        server_name=server,
    )


def _server_cfg(allowlisted: bool = False) -> MCPServerConfig:
    return MCPServerConfig(url="http://localhost:8080/sse", allowlisted=allowlisted)


def _tool_ctx() -> ToolContext:
    return ToolContext(
        user_id="u1",
        session_id="s1",
        session_permission="ReadWrite",
        channel="web",
        route="",
        progress=NoopProgressSink(),
        bearer_token=None,
        memory_root=Path("/tmp"),
        project_root=Path("."),
    )


def _fake_client(tool_defs: list[MCPToolDef], invoke_result: Any = "ok") -> Any:
    client = MagicMock()
    client.list_tools = AsyncMock(return_value=tool_defs)
    client.invoke = AsyncMock(return_value=invoke_result)
    return client


# ─── mcp_tool_name ────────────────────────────────────────────────────────────


def test_mcp_tool_name_format():
    assert mcp_tool_name("fmp", "get_quote") == "mcp__fmp__get_quote"


def test_mcp_tool_name_strips_no_extra():
    assert mcp_tool_name("server", "tool") == "mcp__server__tool"


# ─── parse_mcp_servers_env — JSON ─────────────────────────────────────────────


def test_parse_empty_string_returns_empty():
    assert parse_mcp_servers_env("") == {}


def test_parse_json_url_only():
    raw = json.dumps({"fmp": {"url": "http://localhost:8080/sse"}})
    servers = parse_mcp_servers_env(raw)
    assert "fmp" in servers
    assert servers["fmp"].url == "http://localhost:8080/sse"
    assert servers["fmp"].auth_token == ""
    assert servers["fmp"].allowlisted is False


def test_parse_json_full_config():
    raw = json.dumps(
        {
            "fmp": {
                "url": "http://localhost:8080/sse",
                "auth_token": "tok123",
                "timeout_s": 60.0,
                "allowlisted": True,
            }
        }
    )
    servers = parse_mcp_servers_env(raw)
    cfg = servers["fmp"]
    assert cfg.auth_token == "tok123"
    assert cfg.timeout_s == 60.0
    assert cfg.allowlisted is True


def test_parse_json_string_url_shorthand():
    raw = json.dumps({"fmp": "http://localhost:8080/sse"})
    servers = parse_mcp_servers_env(raw)
    assert servers["fmp"].url == "http://localhost:8080/sse"


def test_parse_json_multiple_servers():
    raw = json.dumps(
        {
            "fmp": {"url": "http://a/sse"},
            "other": {"url": "http://b/sse"},
        }
    )
    servers = parse_mcp_servers_env(raw)
    assert set(servers.keys()) == {"fmp", "other"}


def test_parse_json_invalid_returns_empty():
    assert parse_mcp_servers_env("{bad json") == {}


# ─── parse_mcp_servers_env — CSV shorthand ────────────────────────────────────


def test_parse_csv_single():
    servers = parse_mcp_servers_env("fmp:http://localhost:8080/sse")
    assert servers["fmp"].url == "http://localhost:8080/sse"


def test_parse_csv_multiple():
    servers = parse_mcp_servers_env("fmp:http://a/sse,other:http://b/sse")
    assert "fmp" in servers and "other" in servers


def test_parse_csv_ignores_blank_entries():
    servers = parse_mcp_servers_env("fmp:http://a/sse,,other:http://b/sse")
    assert len(servers) == 2


def test_parse_csv_bad_entry_skipped():
    servers = parse_mcp_servers_env("bad_no_colon,fmp:http://a/sse")
    assert "fmp" in servers
    assert "bad_no_colon" not in servers


# ─── load_mcp_config ──────────────────────────────────────────────────────────


def test_load_mcp_config_disabled_when_no_env(monkeypatch):
    monkeypatch.delenv("MCP_SERVERS", raising=False)
    cfg = load_mcp_config()
    assert cfg.enabled is False
    assert cfg.servers == {}


def test_load_mcp_config_enabled_when_set(monkeypatch):
    monkeypatch.setenv("MCP_SERVERS", "fmp:http://localhost:8080/sse")
    # `ai.mcp.config` keeps a reference to the process `mcp_config` snapshot from
    # import time; env changes alone do not update it — align the module binding with
    # a fresh load after setenv (same pattern as production would need a reload).
    monkeypatch.setattr(ai_mcp_config_mod, "mcp_config", load(MCPEnvConfig))
    cfg = load_mcp_config()
    assert cfg.enabled is True
    assert "fmp" in cfg.servers


# ─── MCPToolBridge — construction ─────────────────────────────────────────────


def test_bridge_name_prefixed():
    bridge = MCPToolBridge(_tool_def(), _fake_client([]), _server_cfg())
    assert bridge.name == "mcp__fmp__get_quote"


def test_bridge_description():
    bridge = MCPToolBridge(_tool_def(name="my_tool"), _fake_client([]), _server_cfg())
    assert "my_tool" in bridge.description


def test_bridge_schema_passthrough():
    td = _tool_def()
    bridge = MCPToolBridge(td, _fake_client([]), _server_cfg())
    assert bridge.parameters_json_schema == td.input_schema


def test_bridge_schema_fallback_for_empty_schema():
    td = MCPToolDef(name="t", description="d", input_schema={}, server_name="s")
    bridge = MCPToolBridge(td, _fake_client([]), _server_cfg())
    schema = bridge.parameters_json_schema
    assert schema.get("type") == "object"


def test_bridge_permission_readonly_by_default():
    bridge = MCPToolBridge(_tool_def(), _fake_client([]), _server_cfg(allowlisted=False))
    assert bridge.required_permission == PermissionMode.ReadOnly


def test_bridge_permission_workspace_write_when_allowlisted():
    bridge = MCPToolBridge(_tool_def(), _fake_client([]), _server_cfg(allowlisted=True))
    assert bridge.required_permission == PermissionMode.WorkspaceWrite


# ─── MCPToolBridge — execute ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bridge_execute_calls_invoke():
    client = _fake_client([_tool_def()], invoke_result="price: 150")
    bridge = MCPToolBridge(_tool_def(), client, _server_cfg())
    result = await bridge._execute(_tool_ctx(), {"ticker": "AAPL"})
    assert result.ok
    assert result.data == "price: 150"
    client.invoke.assert_awaited_once_with("fmp", bridge._server_cfg, "get_quote", {"ticker": "AAPL"})


@pytest.mark.asyncio
async def test_bridge_execute_handles_invoke_exception():
    client = MagicMock()
    client.invoke = AsyncMock(side_effect=RuntimeError("timeout"))
    bridge = MCPToolBridge(_tool_def(), client, _server_cfg())
    result = await bridge._execute(_tool_ctx(), {})
    assert not result.ok
    assert result.error["code"] == "mcp_invoke_error"
    assert "timeout" in result.error["message"]


@pytest.mark.asyncio
async def test_bridge_execute_handles_import_error():
    client = MagicMock()
    client.invoke = AsyncMock(side_effect=ImportError("mcp not installed"))
    bridge = MCPToolBridge(_tool_def(), client, _server_cfg())
    result = await bridge._execute(_tool_ctx(), {})
    assert not result.ok
    assert result.error["code"] == "mcp_not_installed"


@pytest.mark.asyncio
async def test_bridge_openai_tool_schema():
    bridge = MCPToolBridge(_tool_def(), _fake_client([]), _server_cfg())
    tool_def = bridge.openai_tool()
    assert tool_def["type"] == "function"
    assert tool_def["function"]["name"] == "mcp__fmp__get_quote"
    assert "parameters" in tool_def["function"]


# ─── load_mcp_tools ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_load_mcp_tools_empty_when_disabled():
    cfg = MCPConfig(servers={}, enabled=False)
    tools = await load_mcp_tools(cfg=cfg)
    assert tools == []


@pytest.mark.asyncio
async def test_load_mcp_tools_returns_bridges():
    cfg = MCPConfig(
        servers={"fmp": MCPServerConfig(url="http://localhost/sse")},
        enabled=True,
    )
    td = _tool_def("get_quote", "fmp")
    client = _fake_client([td])
    tools = await load_mcp_tools(client=client, cfg=cfg)
    assert len(tools) == 1
    assert tools[0].name == "mcp__fmp__get_quote"


@pytest.mark.asyncio
async def test_load_mcp_tools_multiple_servers():
    cfg = MCPConfig(
        servers={
            "fmp": MCPServerConfig(url="http://a/sse"),
            "other": MCPServerConfig(url="http://b/sse"),
        },
        enabled=True,
    )
    client = MagicMock()

    async def _list_tools(server_name, server_cfg):
        return [_tool_def("tool_a", server_name)]

    client.list_tools = _list_tools
    tools = await load_mcp_tools(client=client, cfg=cfg)
    assert len(tools) == 2
    names = {t.name for t in tools}
    assert "mcp__fmp__tool_a" in names
    assert "mcp__other__tool_a" in names


@pytest.mark.asyncio
async def test_load_mcp_tools_skips_failed_server():
    cfg = MCPConfig(
        servers={
            "bad": MCPServerConfig(url="http://bad/sse"),
            "good": MCPServerConfig(url="http://good/sse"),
        },
        enabled=True,
    )
    client = MagicMock()

    async def _list_tools(server_name, server_cfg):
        if server_name == "bad":
            raise ConnectionError("refused")
        return [_tool_def("t", server_name)]

    client.list_tools = _list_tools
    tools = await load_mcp_tools(client=client, cfg=cfg)
    assert len(tools) == 1
    assert tools[0].name == "mcp__good__t"


@pytest.mark.asyncio
async def test_load_mcp_tools_empty_tool_list_per_server():
    cfg = MCPConfig(servers={"fmp": MCPServerConfig(url="http://a/sse")}, enabled=True)
    client = _fake_client([])
    tools = await load_mcp_tools(client=client, cfg=cfg)
    assert tools == []


# ─── lazy import: mcp SDK not imported on module load ─────────────────────────


def test_mcp_sdk_not_imported_at_module_load():
    """Importing mcp_bridge + mcp.client must NOT pull in the mcp SDK."""
    import sys
    import importlib

    importlib.import_module("ai.mcp")
    importlib.import_module("ai.mcp.config")
    importlib.import_module("ai.mcp.client")
    importlib.import_module("ai.tools.mcp_bridge")
    assert "mcp" not in sys.modules, "mcp SDK imported eagerly — must be lazy"


# ─── MCPClient raises ImportError without SDK ─────────────────────────────────


@pytest.mark.asyncio
async def test_mcp_client_raises_import_error_without_sdk():
    import sys

    sdk_mod = sys.modules.pop("mcp", None)
    try:
        from ai.mcp.client import MCPClient

        client = MCPClient()
        with pytest.raises(ImportError, match="mcp"):
            await client.list_tools("test", MCPServerConfig(url="http://x/sse"))
    finally:
        if sdk_mod is not None:
            sys.modules["mcp"] = sdk_mod


# ─── _extract_content helper ──────────────────────────────────────────────────


def test_extract_content_empty():
    from ai.mcp.client import _extract_content

    assert _extract_content([]) == ""
    assert _extract_content(None) == ""


def test_extract_content_single_text_block():
    from ai.mcp.client import _extract_content

    class Block:
        text = "hello"

    assert _extract_content([Block()]) == "hello"


def test_extract_content_multiple_text_blocks():
    from ai.mcp.client import _extract_content

    class Block:
        def __init__(self, t):
            self.text = t

    result = _extract_content([Block("a"), Block("b")])
    assert result == "a\nb"


def test_extract_content_non_text_block_repr():
    from ai.mcp.client import _extract_content

    class ImageBlock:
        pass  # no .text

    result = _extract_content([ImageBlock()])
    assert "ImageBlock" in result
