"""Lazy-loaded dispatch table for Phase 14 route handlers.

Handlers are imported on first call so that importing ``dispatch`` does not
eagerly load all handler modules (some have heavy optional dependencies).
The global ``_handlers`` cache is reset between tests via ``_reset_handlers()``.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from ai.routes.context import RouteContext, RouteResult

logger = logging.getLogger(__name__)

_handlers: Optional[dict[str, Callable]] = None


def _build_handlers() -> dict[str, Callable]:
    from ai.routes.actions_catchup import run as _actions_catchup
    from ai.routes.actions_market_catchup import run as _actions_market_catchup
    from ai.routes.action_tldr_news import run as _action_tldr_news
    from ai.routes.actions_recent_earnings import run as _actions_recent_earnings
    from ai.routes.spaces_discover import run as _spaces_discover
    from ai.routes.spaces_kb_refresh import run as _spaces_kb_refresh
    from ai.routes.spaces_summary import run as _spaces_summary
    from ai.routes.spaces_compact import run as _spaces_compact
    from ai.routes.spaces_youtube_summary import run as _spaces_youtube_summary
    from ai.routes.heartbeat_extract import run as _heartbeat_extract
    from ai.routes.memory_weekly_synthesis import run as _memory_weekly_synthesis
    from ai.routes.memory_decay_tick import run as _memory_decay_tick
    from ai.routes.llm_council import run as _llm_council

    return {
        "actions-catchup": _actions_catchup,
        "actions-market-catchup": _actions_market_catchup,
        "action-tldr-news": _action_tldr_news,
        "actions-recent-earnings": _actions_recent_earnings,
        "spaces-discover": _spaces_discover,
        "spaces-knowledge-base-sources-refresh": _spaces_kb_refresh,
        "spaces-summary": _spaces_summary,
        "spaces-compact": _spaces_compact,
        "spaces-youtube-summary": _spaces_youtube_summary,
        "heartbeat-extract": _heartbeat_extract,
        "memory-weekly-synthesis": _memory_weekly_synthesis,
        "memory-decay-tick": _memory_decay_tick,
        "llm-council": _llm_council,
    }


def _get_handlers() -> dict[str, Callable]:
    global _handlers
    if _handlers is None:
        _handlers = _build_handlers()
    return _handlers


def _reset_handlers() -> None:
    """Clear the handler cache (test helper)."""
    global _handlers
    _handlers = None


async def dispatch(route: str, ctx: RouteContext) -> RouteResult:
    """Look up and call the handler for *route*.

    Returns a ``RouteResult(ok=False)`` on unknown routes or unhandled
    exceptions — never raises.
    """
    handler = _get_handlers().get(route)
    if handler is None:
        logger.warning("no handler for route %r", route)
        return RouteResult(
            text=f"Unknown route: {route!r}",
            ok=False,
            error="unknown_route",
        )
    try:
        return await handler(ctx)
    except Exception as exc:  # noqa: BLE001
        logger.exception("route %r handler raised", route)
        return RouteResult(
            text=f"Route {route!r} failed: {exc}",
            ok=False,
            error=str(type(exc).__name__),
        )
