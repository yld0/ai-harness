"""Bridge: theses_* ↔ thesis.md  (file wins, user-authored).  Stub."""

from __future__ import annotations

from ai.memory.bridges.base import NotImplementedBridge


class ThesesBridge(NotImplementedBridge):
    direction = "both"
    gql_surface = "theses"
    conflict_rule = "file_wins"
