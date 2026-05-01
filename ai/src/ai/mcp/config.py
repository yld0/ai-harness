"""
MCP server configuration.

Server list is defined on :class:`~ai.config.MCPConfig` (``MCP_SERVERS`` env)
and loaded via :func:`shared.envutil.config.load`.  Two formats accepted:

1. **JSON object** — full control::

       MCP_SERVERS='{"fmp": {"url": "http://localhost:8080/sse", "auth_token": "tok", "timeout_s": 30, "allowlisted": false}}'

2. **Shorthand CSV** — ``name:url`` pairs, one per comma::

       MCP_SERVERS='fmp:http://localhost:8080/sse,other:http://localhost:8081/sse'

When ``MCP_SERVERS`` is absent or empty, MCP integration is disabled and no
heavy SDK imports occur.

:func:`load_mcp_config` calls :func:`~shared.envutil.config.load` on each
invocation so tests and runtime see the current environment.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from ai.config import mcp_config

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Per-server connection settings."""

    url: str
    auth_token: str = ""
    timeout_s: float = 30.0
    # When True the server's tools inherit WorkspaceWrite permission; otherwise ReadOnly.
    allowlisted: bool = False


@dataclass
class MCPConfig:
    """Resolved MCP configuration."""

    servers: dict[str, MCPServerConfig] = field(default_factory=dict)
    enabled: bool = False


def parse_mcp_servers_env(raw: str) -> dict[str, MCPServerConfig]:
    """Parse ``MCP_SERVERS`` value into a ``{name: MCPServerConfig}`` dict.

    Returns an empty dict on any parse error (logs a warning).
    """
    raw = raw.strip()
    if not raw:
        return {}

    # Attempt JSON first.
    if raw.startswith("{"):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("MCP_SERVERS is invalid JSON (%s); MCP disabled", exc)
            return {}
        if not isinstance(parsed, dict):
            logger.warning("MCP_SERVERS JSON must be an object; MCP disabled")
            return {}
        servers: dict[str, MCPServerConfig] = {}
        for name, val in parsed.items():
            if isinstance(val, str):
                servers[name] = MCPServerConfig(url=val)
            elif isinstance(val, dict):
                try:
                    servers[name] = MCPServerConfig(
                        url=val["url"],
                        auth_token=str(val.get("auth_token", "")),
                        timeout_s=float(val.get("timeout_s", 30.0)),
                        allowlisted=bool(val.get("allowlisted", False)),
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    logger.warning("MCP_SERVERS: bad entry %r (%s); skipping", name, exc)
            else:
                logger.warning("MCP_SERVERS: unrecognised entry type for %r; skipping", name)
        return servers

    # CSV shorthand: "name:url,name2:url2"
    servers = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        colon = part.find(":")
        if colon <= 0:
            logger.warning("MCP_SERVERS: cannot parse entry %r (expected name:url); skipping", part)
            continue
        name = part[:colon].strip()
        url = part[colon + 1 :].strip()
        if not url:
            logger.warning("MCP_SERVERS: empty URL for server %r; skipping", name)
            continue
        servers[name] = MCPServerConfig(url=url)
    return servers


def load_mcp_config() -> MCPConfig:
    """Read :class:`~ai.config.MCPConfig` and build an :class:`MCPConfig`."""
    raw = mcp_config.MCP_SERVERS
    if not raw.strip():
        return MCPConfig(servers={}, enabled=False)
    servers = parse_mcp_servers_env(raw)
    return MCPConfig(servers=servers, enabled=bool(servers))
