"""Route name → handler module path; dispatched via ``ai.routes.dispatch``."""

from __future__ import annotations

from typing import Any, Final, Literal, TypedDict

# Routes named in `plans/07-phase-6-financial-tools.md` + linked phases.
# Values are import paths for the lazy handler modules (Phase 14 real handlers).
ROUTE_MODULE_PATHS: Final[dict[str, str]] = {
    "actions-catchup": "ai.routes.actions_catchup",
    "actions-market-catchup": "ai.routes.actions_market_catchup",
    "action-tldr-news": "ai.routes.action_tldr_news",
    "actions-recent-earnings": "ai.routes.actions_recent_earnings",
    "spaces-discover": "ai.routes.spaces_discover",
    "spaces-knowledge-base-sources-refresh": "ai.routes.spaces_kb_refresh",
    "spaces-summary": "ai.routes.spaces_summary",
    "spaces-compact": "ai.routes.spaces_compact",
    "spaces-youtube-summary": "ai.routes.spaces_youtube_summary",
    "llm-council": "ai.routes.llm_council",
    "general-research": "ai.routes.handlers.not_implemented",
    "heartbeat-extract": "ai.routes.heartbeat_extract",
    "memory-weekly-synthesis": "ai.routes.memory_weekly_synthesis",
    "memory-decay-tick": "ai.routes.memory_decay_tick",
}

RouteState = Literal["not_implemented", "unknown"]


class RouteDispatch(TypedDict):
    name: str
    state: RouteState
    module_path: str | None
    error: dict[str, Any] | None


STABLE_NOT_IMPLEMENTED = "This route is registered but the handler is not implemented yet (Phase 14)."


def resolve_route(name: str | None) -> RouteDispatch:
    if not name:
        return {
            "name": "",
            "state": "unknown",
            "module_path": None,
            "error": {"code": "route_required", "message": "No route was provided."},
        }
    if name not in ROUTE_MODULE_PATHS:
        return {
            "name": name,
            "state": "unknown",
            "module_path": None,
            "error": {
                "code": "unknown_route",
                "message": f"Route {name!r} is not a registered harness route.",
            },
        }
    return {
        "name": name,
        "state": "not_implemented",
        "module_path": ROUTE_MODULE_PATHS[name],
        "error": {
            "code": "not_implemented",
            "message": STABLE_NOT_IMPLEMENTED,
        },
    }
