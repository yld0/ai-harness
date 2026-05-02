"""Bridge ABC, result types, and NotImplementedBridge base for stubs.

All bridge implementations inherit from ``Bridge``.  Stub bridges use the
``NotImplementedBridge`` shorthand — they register correctly so the registry
is complete but return a ``not_implemented`` status on any operation.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

from ai.memory.para import ParaMemoryLayout

logger = logging.getLogger(__name__)

ConflictRule = Literal["gql_wins", "file_wins", "last_write_wins"]


@dataclass
class PullResult:
    """Result of a bridge pull (GQL → disk)."""

    ok: bool
    records_written: int = 0
    detail: str = ""
    prompt_block: str = ""  # Non-empty only for the memories_* bridge
    error: Optional[str] = None


@dataclass
class PushResult:
    """Result of a bridge push (disk → GQL)."""

    ok: bool
    records_pushed: int = 0
    detail: str = ""
    error: Optional[str] = None


class Bridge(ABC):
    """Bidirectional or one-way bridge between a GQL subgraph and on-disk PARA memory.

    Subclasses declare three class-level attributes:
        direction:      "pull", "push", or "both"
        gql_surface:    GQL type prefix, e.g. "memories", "rules"
        conflict_rule:  How to resolve file ↔ GQL conflicts
    """

    direction: Literal["pull", "push", "both"]
    gql_surface: str
    conflict_rule: ConflictRule

    @abstractmethod
    async def pull(
        self,
        user_id: str,
        bearer_token: str,
        *,
        layout: ParaMemoryLayout,
        client: Optional[Any] = None,
    ) -> PullResult:
        """Fetch from GraphQL and persist to disk (or build prompt block).

        Implementations must not raise — return PullResult(ok=False, error=…) instead.
        """

    async def push(
        self,
        file_path: Path,
        user_id: str,
        bearer_token: str,
        *,
        layout: ParaMemoryLayout,
        client: Optional[Any] = None,
    ) -> PushResult:
        """Read from disk and write to GraphQL.

        Default implementation returns not_implemented.  Override for bridges
        whose ``direction`` is "push" or "both".
        """
        return PushResult(ok=False, detail="push_not_implemented", error="push_not_implemented")


class NotImplementedBridge(Bridge):
    """Stub bridge for surfaces not yet wired to a real subgraph query.

    Registers in the registry so the complete 11-surface set is always present.
    Returns not_implemented status without crashing.
    """

    conflict_rule: ConflictRule = "gql_wins"

    async def pull(
        self,
        user_id: str,
        bearer_token: str,
        *,
        layout: ParaMemoryLayout,
        client: Optional[Any] = None,
    ) -> PullResult:
        logger.debug("bridge %s pull: not_implemented", self.gql_surface)
        return PullResult(ok=False, detail="not_implemented", error="not_implemented")

    async def push(
        self,
        file_path: Path,
        user_id: str,
        bearer_token: str,
        *,
        layout: ParaMemoryLayout,
        client: Optional[Any] = None,
    ) -> PushResult:
        logger.debug("bridge %s push: not_implemented", self.gql_surface)
        return PushResult(ok=False, detail="not_implemented", error="not_implemented")
