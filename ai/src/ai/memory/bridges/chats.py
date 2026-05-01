"""Bridge: chats_* → daily-note pointer  (pull only, GQL wins).  Stub."""

from __future__ import annotations

from ai.memory.bridges.base import NotImplementedBridge


class ChatsBridge(NotImplementedBridge):
    direction = "pull"
    gql_surface = "chats"
    conflict_rule = "gql_wins"
