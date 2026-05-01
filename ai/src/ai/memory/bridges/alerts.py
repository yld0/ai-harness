"""Bridge: alerts_* → alerts.yaml  (pull only, GQL wins)."""

from __future__ import annotations

import logging
from typing import Any, Optional

import yaml

from ai.clients.alerts import fetch_alerts
from ai.memory.bridges.base import Bridge, PullResult, PushResult
from ai.memory.para import ParaMemoryLayout

logger = logging.getLogger(__name__)


class AlertsBridge(Bridge):
    """Pull-only alerts bridge."""

    direction = "pull"
    gql_surface = "alerts"
    conflict_rule = "gql_wins"

    async def pull(
        self,
        user_id: str,
        bearer_token: str,
        *,
        layout: ParaMemoryLayout,
        client: Optional[Any] = None,
    ) -> PullResult:
        try:
            records = await fetch_alerts(bearer_token, client=client)
        except Exception as exc:  # noqa: BLE001
            logger.warning("alerts_* pull failed for user %s: %s", user_id, exc)
            return PullResult(ok=False, detail=str(exc), error=str(exc))

        alerts_path = layout.guarded_user_path(user_id, "life", "alerts.yaml")
        alerts_path.parent.mkdir(parents=True, exist_ok=True)
        with alerts_path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(records, fh, default_flow_style=False, allow_unicode=True)

        return PullResult(ok=True, records_written=len(records))
