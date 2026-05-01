"""Process-local bridge registry and eager registration of built-in surfaces."""

from __future__ import annotations

from typing import Optional

from ai.memory.bridges.alerts import AlertsBridge
from ai.memory.bridges.base import Bridge
from ai.memory.bridges.chats import ChatsBridge
from ai.memory.bridges.consensus import ConsensusBridge
from ai.memory.bridges.goals import GoalsBridge
from ai.memory.bridges.memories import MemoriesBridge
from ai.memory.bridges.rules import RulesBridge
from ai.memory.bridges.spaces import SpacesBridge
from ai.memory.bridges.spaces_sources import SpacesSourcesBridge
from ai.memory.bridges.theses import ThesesBridge
from ai.memory.bridges.valuations import ValuationsBridge
from ai.memory.bridges.watchlists import WatchlistsBridge

_REGISTRY: dict[str, Bridge] = {}


def _register(bridge: Bridge) -> Bridge:
    _REGISTRY[bridge.gql_surface] = bridge
    return bridge


def get_bridge(surface: str) -> Optional[Bridge]:
    """Return the bridge registered for *surface*, or None."""
    return _REGISTRY.get(surface)


def all_bridges() -> list[Bridge]:
    """Return a snapshot of all registered bridges."""
    return list(_REGISTRY.values())


_register(MemoriesBridge())
_register(RulesBridge())
_register(ValuationsBridge())
_register(ConsensusBridge())
_register(ThesesBridge())
_register(GoalsBridge())
_register(SpacesBridge())
_register(SpacesSourcesBridge())
_register(ChatsBridge())
_register(WatchlistsBridge())
_register(AlertsBridge())
