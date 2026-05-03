"""MCP client — connects to an SSE MCP server, lists tools, and invokes them.

The ``mcp`` Python SDK is imported lazily so that this module is safe to import
even when the optional ``mcp`` extra is not installed.  The import only happens
when :meth:`MCPClient.list_tools` or :meth:`MCPClient.invoke` is actually called.

Install the extra to use live servers::

    uv add 'ai[mcp]'   # or: pip install 'ai[mcp]'
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ai.mcp.config import MCPServerConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MCPToolDef:
    """Descriptor for a single tool discovered from an MCP server."""

    name: str  # tool's original name as advertised by the server
    description: str
    input_schema: dict[str, Any]
    server_name: str  # the logical server name (key in MCPConfig.servers)


class MCPClient:
    """Thin async wrapper around the MCP Python SDK (SSE transport).

    All SDK imports are deferred to :meth:`_list_tools_via_sdk` and
    :meth:`_invoke_via_sdk` so the class is importable without ``mcp`` installed.
    """

    async def list_tools(
        self,
        server_name: str,
        cfg: MCPServerConfig,
    ) -> list[MCPToolDef]:
        """Discover tools on *server_name*."""
        return await self._list_tools_via_sdk(server_name, cfg)

    async def invoke(
        self,
        server_name: str,
        cfg: MCPServerConfig,
        tool_name: str,
        args: dict[str, Any],
    ) -> Any:
        """Call *tool_name* with *args* on *server_name* and return the result content."""
        return await self._invoke_via_sdk(server_name, cfg, tool_name, args)

    # ── SDK implementation (only called when mcp extra is installed) ────────────

    async def _list_tools_via_sdk(self, server_name: str, cfg: MCPServerConfig) -> list[MCPToolDef]:
        try:
            from mcp import ClientSession  # type: ignore[import]
            from mcp.client.sse import sse_client  # type: ignore[import]
        except ImportError as exc:
            raise ImportError("The 'mcp' extra is required for MCP integration. Install it with: uv add 'ai[mcp]'  (or: pip install 'ai[mcp]')") from exc

        headers = _auth_headers(cfg)
        async with sse_client(cfg.url, headers=headers, timeout=cfg.timeout_s) as (
            read,
            write,
        ):
            async with ClientSession(read, write) as session:
                await session.initialize()
                response = await session.list_tools()
                return [
                    MCPToolDef(
                        name=t.name,
                        description=t.description or "",
                        input_schema=(t.inputSchema if isinstance(t.inputSchema, dict) else {}),
                        server_name=server_name,
                    )
                    for t in (response.tools or [])
                ]

    async def _invoke_via_sdk(
        self,
        server_name: str,
        cfg: MCPServerConfig,
        tool_name: str,
        args: dict[str, Any],
    ) -> Any:
        try:
            from mcp import ClientSession  # type: ignore[import]
            from mcp.client.sse import sse_client  # type: ignore[import]
        except ImportError as exc:
            raise ImportError("The 'mcp' extra is required for MCP integration. Install it with: uv add 'ai[mcp]'  (or: pip install 'ai[mcp]')") from exc

        headers = _auth_headers(cfg)
        async with sse_client(cfg.url, headers=headers, timeout=cfg.timeout_s) as (
            read,
            write,
        ):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)
                # result.content is a list of ContentBlock; extract text parts.
                return _extract_content(result.content)


def _auth_headers(cfg: MCPServerConfig) -> dict[str, str]:
    if cfg.auth_token:
        return {"Authorization": f"Bearer {cfg.auth_token}"}
    return {}


def _extract_content(content: Any) -> Any:
    """Flatten MCP ContentBlock list → str or list of str."""
    if not content:
        return ""
    # SDK ContentBlock objects have a `text` attribute for text blocks.
    parts: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(str(text))
        else:
            # Non-text block (image, etc.) — return repr.
            parts.append(repr(block))
    return "\n".join(parts) if len(parts) > 1 else (parts[0] if parts else "")
