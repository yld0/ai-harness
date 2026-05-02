"""Bridge: watchlists_* ↔ items.yaml  (GQL wins).

Pull: fetch ``watchlists_watchlists``, write each watchlist's assets to
``users/<uid>/life/watchlists/<watchlist_id>/items.yaml``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import yaml

from ai.memory.bridges.base import Bridge, PullResult, PushResult
from ai.memory.para import ParaMemoryLayout

logger = logging.getLogger(__name__)

WATCHLISTS_QUERY = """
query GetWatchlists {
  watchlists_watchlists {
    watchlists {
      id
      name
      description
      assets {
        symbol
        displayOrder
      }
      updatedAt
    }
    returnedCount
  }
}
"""


class WatchlistsBridge(Bridge):
    """GQL-wins watchlists bridge."""

    direction = "both"
    gql_surface = "watchlists"
    conflict_rule = "gql_wins"

    async def pull(
        self,
        user_id: str,
        bearer_token: str,
        *,
        layout: ParaMemoryLayout,
        client: Optional[Any] = None,
    ) -> PullResult:
        from ai.clients.transport import GraphqlClient

        gql: Any = client or GraphqlClient()
        try:
            data = await gql.execute(WATCHLISTS_QUERY, bearer_token=bearer_token)
        except Exception as exc:  # noqa: BLE001
            logger.warning("watchlists_* pull failed for user %s: %s", user_id, exc)
            return PullResult(ok=False, detail=str(exc), error=str(exc))

        raw: list[dict] = (data.get("watchlists_watchlists") or {}).get("watchlists") or []
        written = 0
        for wl in raw:
            if not isinstance(wl, dict):
                continue
            wl_id = wl.get("id") or ""
            if not wl_id:
                continue
            try:
                items_path = layout.entity_dir(user_id, "watchlists", wl_id) / "items.yaml"
                items_path.parent.mkdir(parents=True, exist_ok=True)
                _write_items_yaml(items_path, wl)
                written += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("failed to write watchlist %s: %s", wl_id, exc)

        return PullResult(ok=True, records_written=written)

    async def push(
        self,
        file_path: Path,
        user_id: str,
        bearer_token: str,
        *,
        layout: ParaMemoryLayout,
        client: Optional[Any] = None,
    ) -> PushResult:
        # GQL is source of truth; push is not applicable
        return PushResult(ok=False, detail="not_implemented", error="not_implemented")


def _write_items_yaml(path: Path, watchlist: dict[str, Any]) -> None:
    assets = watchlist.get("assets") or []
    record = {
        "watchlist_id": watchlist.get("id"),
        "name": watchlist.get("name"),
        "description": watchlist.get("description"),
        "updated_at": watchlist.get("updatedAt"),
        "assets": [{"symbol": a.get("symbol"), "display_order": a.get("displayOrder")} for a in assets if isinstance(a, dict)],
    }
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(record, fh, default_flow_style=False, allow_unicode=True)
