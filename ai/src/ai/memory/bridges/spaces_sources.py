"""Bridge: spaces_sources_* ↔ sources.yaml  (GQL wins).  Stub."""

from __future__ import annotations

from ai.memory.bridges.base import NotImplementedBridge


class SpacesSourcesBridge(NotImplementedBridge):
    direction = "both"
    gql_surface = "spaces_sources"
    conflict_rule = "gql_wins"
