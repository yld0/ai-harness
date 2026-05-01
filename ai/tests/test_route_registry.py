"""Route registry stubs (Phase 6)."""

from ai.routes.registry import ROUTE_MODULE_PATHS, STABLE_NOT_IMPLEMENTED, resolve_route


def test_all_routes_registered() -> None:
    expected = {
        "actions-catchup",
        "actions-market-catchup",
        "action-tldr-news",
        "actions-recent-earnings",
        "spaces-discover",
        "spaces-knowledge-base-sources-refresh",
        "spaces-summary",
        "spaces-compact",
        "spaces-youtube-summary",
        "llm-council",
        "general-research",
        "heartbeat-extract",
        "memory-weekly-synthesis",
        "memory-decay-tick",
    }
    assert set(ROUTE_MODULE_PATHS) == expected


def test_resolve_known_route_not_implemented() -> None:
    r = resolve_route("general-research")
    assert r["state"] == "not_implemented"
    assert r["error"] is not None
    assert r["error"]["code"] == "not_implemented"
    assert STABLE_NOT_IMPLEMENTED in r["error"]["message"]


def test_resolve_unknown_route() -> None:
    r = resolve_route("not-a-route")
    assert r["state"] == "unknown"
    assert r["error"] is not None
    assert r["error"]["code"] == "unknown_route"
