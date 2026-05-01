"""MCP → internal Tool bridge (Phase 20).

:func:`load_mcp_tools` discovers tools from all configured MCP servers and
returns a list of :class:`MCPToolBridge` instances that integrate seamlessly
with the existing ``Tool`` / ``ToolRegistry`` machinery.

Tool names are prefixed: ``mcp__<server_name>__<original_tool_name>``.

Permission default is ``ReadOnly`` unless the server is explicitly allowlisted
(``allowlisted: true`` in ``MCPServerConfig``), in which case ``WorkspaceWrite``
is granted.

When :class:`~ai.config.MCPConfig` ``MCP_SERVERS`` is empty the function
returns an empty list and no MCP
SDK import occurs — zero overhead for the common case.
"""

from __future__ import annotations

import logging
from typing import Any

from ai.mcp.config import MCPServerConfig, load_mcp_config
from ai.mcp.client import MCPClient, MCPToolDef
from ai.tools.base import Tool, ToolResult, err_result, ok_result
from ai.tools.context import ToolContext
from ai.tools.permissions import PermissionMode

logger = logging.getLogger(__name__)

_MCP_NAME_SEP = "__"


def mcp_tool_name(server_name: str, tool_name: str) -> str:
    """Return the prefixed tool name: ``mcp__<server>__<tool>``."""
    return f"mcp{_MCP_NAME_SEP}{server_name}{_MCP_NAME_SEP}{tool_name}"


class MCPToolBridge(Tool):
    """Adapts a single MCP tool to the internal :class:`~ai.tools.base.Tool` interface.

    Instance attributes override the class-level ``ClassVar`` annotations because
    MCP tool names/descriptions are dynamic (discovered at runtime, not coded as
    class constants).
    """

    file_component_risk = False  # MCP tools don't touch the local filesystem directly

    def __init__(
        self,
        tool_def: MCPToolDef,
        client: Any,  # MCPClient or any duck-typed mock
        server_cfg: MCPServerConfig,
    ) -> None:
        self.name: str = mcp_tool_name(tool_def.server_name, tool_def.name)  # type: ignore[misc]
        self.description: str = tool_def.description or f"MCP tool {tool_def.name}"  # type: ignore[misc]
        self._tool_def = tool_def
        self._client = client
        self._server_cfg = server_cfg
        self.required_permission: PermissionMode = (  # type: ignore[misc]
            PermissionMode.WorkspaceWrite if server_cfg.allowlisted else PermissionMode.ReadOnly
        )

    @property
    def parameters_json_schema(self) -> dict[str, Any]:
        schema = self._tool_def.input_schema
        if not isinstance(schema, dict) or "type" not in schema:
            return {"type": "object", "properties": {}}
        return schema

    async def _execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        try:
            result = await self._client.invoke(
                self._tool_def.server_name,
                self._server_cfg,
                self._tool_def.name,
                args,
            )
        except ImportError as exc:
            return err_result("mcp_not_installed", str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("MCP tool %s invoke failed", self.name)
            return err_result("mcp_invoke_error", f"{type(exc).__name__}: {exc}")
        return ok_result(result)


async def load_mcp_tools(
    client: Any | None = None,
    cfg: Any | None = None,
) -> list[MCPToolBridge]:
    """Discover and return all MCP tool bridges.

    Parameters
    ----------
    client:
        Optional :class:`~ai.mcp.client.MCPClient` override (useful in tests).
    cfg:
        Optional :class:`~ai.mcp.config.MCPConfig` override (useful in tests).

    Returns an empty list (and does NO SDK import) when MCP is disabled.
    """
    resolved_cfg = cfg if cfg is not None else load_mcp_config()
    if not resolved_cfg.enabled:
        return []

    resolved_client = client if client is not None else MCPClient()

    bridges: list[MCPToolBridge] = []
    for server_name, server_cfg in resolved_cfg.servers.items():
        try:
            tool_defs = await resolved_client.list_tools(server_name, server_cfg)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "MCP: failed to list tools for server %r (%s); skipping",
                server_name,
                exc,
            )
            continue
        for tool_def in tool_defs:
            bridges.append(MCPToolBridge(tool_def, resolved_client, server_cfg))
            logger.debug("MCP: registered tool %s", mcp_tool_name(server_name, tool_def.name))

    logger.info(
        "MCP: loaded %d tool(s) from %d server(s)",
        len(bridges),
        len(resolved_cfg.servers),
    )
    return bridges
