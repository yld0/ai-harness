"""Typed client for the ``alerts_*`` GraphQL surface."""

from __future__ import annotations

import logging
from typing import Any

from ai.tools.graphql import GraphqlClient

logger = logging.getLogger(__name__)

ALERTS_QUERY = """
query GetAlerts {
  alerts_alerts {
    alerts {
      id
      enabled
      symbols
      description
      comment
      expireAt
      triggeredAt
      updatedAt
    }
    returnedCount
  }
}
"""


def _normalise_alert(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": raw.get("id"),
        "enabled": raw.get("enabled"),
        "symbols": raw.get("symbols") or [],
        "description": raw.get("description"),
        "comment": raw.get("comment"),
        "expire_at": str(raw.get("expireAt") or ""),
        "triggered_at": str(raw.get("triggeredAt") or ""),
        "updated_at": str(raw.get("updatedAt") or ""),
    }


class AlertsClient:
    """Client for the ``alerts_*`` GraphQL namespace."""

    def __init__(self, client: GraphqlClient | None = None) -> None:
        self._gql = client or GraphqlClient()

    async def fetch_alerts(self, bearer_token: str) -> list[dict[str, Any]]:
        """Fetch all alerts and return normalised records."""
        data = await self._gql.execute(ALERTS_QUERY, bearer_token=bearer_token)
        raw: list[dict] = (data.get("alerts_alerts") or {}).get("alerts") or []
        return [_normalise_alert(a) for a in raw if isinstance(a, dict)]


async def fetch_alerts(
    bearer_token: str,
    *,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    """Convenience wrapper matching the module-level signature used by the bridge."""
    return await AlertsClient(client=client).fetch_alerts(bearer_token)
