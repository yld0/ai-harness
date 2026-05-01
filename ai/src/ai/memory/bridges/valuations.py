"""Bridge: valuations_* ↔ valuation.yaml  (last-write-wins by updatedAt).

GQL surface: not yet present in the supergraph.  File-side operations are
fully implemented; GQL operations return not_implemented and are tracked in
FUTURE.md.

File location: users/<uid>/life/tickers/<SYMBOL>/valuation.yaml
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from ai.memory.bridges.base import Bridge, NotImplementedBridge, PullResult, PushResult
from ai.memory.para import ParaMemoryLayout

logger = logging.getLogger(__name__)


class ValuationsBridge(Bridge):
    """last-write-wins valuation bridge.  GQL side is stubbed; file side is real."""

    direction = "both"
    gql_surface = "valuations"
    conflict_rule = "last_write_wins"

    async def pull(
        self,
        user_id: str,
        bearer_token: str,
        *,
        layout: ParaMemoryLayout,
        client: Optional[Any] = None,
    ) -> PullResult:
        # GQL surface not in supergraph yet
        logger.debug("valuations_* GQL pull: not_implemented (no supergraph surface)")
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
        # GQL surface not in supergraph yet
        logger.debug("valuations_* GQL push: not_implemented (no supergraph surface)")
        return PushResult(ok=False, detail="not_implemented", error="not_implemented")

    # ─── File-side helpers (used directly by other tools) ────────────────── #

    @staticmethod
    def read_valuation(file_path: Path) -> dict[str, Any]:
        """Read valuation.yaml and return its contents as a dict."""
        if not file_path.is_file():
            return {}
        with file_path.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    @staticmethod
    def write_valuation(
        file_path: Path,
        data: dict[str, Any],
        *,
        updated_at: Optional[str] = None,
    ) -> None:
        """Write data to valuation.yaml, injecting updatedAt for conflict resolution."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if updated_at is None:
            updated_at = datetime.now(timezone.utc).isoformat()
        data["updatedAt"] = updated_at
        with file_path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, default_flow_style=False, allow_unicode=True)

    @staticmethod
    def resolve_conflict(
        local: dict[str, Any],
        remote: dict[str, Any],
    ) -> dict[str, Any]:
        """Return whichever side has the later updatedAt timestamp."""
        local_ts = local.get("updatedAt") or ""
        remote_ts = remote.get("updatedAt") or ""
        return remote if remote_ts > local_ts else local
