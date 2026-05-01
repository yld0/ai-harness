"""Bridge: consensus_* → consensus.yaml  (pull only, GQL wins).  Stub."""

from __future__ import annotations

from ai.memory.bridges.base import NotImplementedBridge


class ConsensusBridge(NotImplementedBridge):
    direction = "pull"
    gql_surface = "consensus"
    conflict_rule = "gql_wins"
