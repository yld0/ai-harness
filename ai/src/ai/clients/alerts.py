"""Typed client for the ``alerts_*`` GraphQL surface."""

from __future__ import annotations

from typing import Any

from ai.clients.transport import GraphqlClient

GET_ALERTS_QUERY = """
query GetAlerts($input: AlertsFilterInput) {
  alerts_alerts(input: $input) {
    alerts {
      id
      userID
      enabled
      symbols
      repeated
      expired
      expireAt
      description
      comment
      notificationTypes
      detail {
        ... on PriceTargetAlert {
          alertType
          target
          indicator
        }
        ... on PriceFromCurrentAlert {
          alertType
          priceChange
          price
          indicator
        }
        ... on PercentFromCurrentAlert {
          alertType
          percentChange
          percent
          indicator
        }
        ... on MetricsAlert {
          alertType
          indicator
        }
      }
      group
      tagIDs
      spaceIDs
      createdAt
      updatedAt
      triggeredCount
      triggeredAt
    }
    returnedCount
    totalPossibleCount
  }
}
"""

GET_ALERT_QUERY = """
query GetAlert($alertID: String!) {
  alerts_alert(alertID: $alertID) {
    id
    userID
    enabled
    symbols
    repeated
    expired
    expireAt
    description
    comment
    notificationTypes
    detail {
      ... on PriceTargetAlert {
        alertType
        target
        targetChange
        indicator
      }
      ... on PriceFromCurrentAlert {
        alertType
        priceChange
        price
        indicator
      }
      ... on PercentFromCurrentAlert {
        alertType
        percentChange
        percent
        indicator
      }
      ... on TrailingPriceStopLossAlert {
        alertType
        trailingStopLossType
        trailing
        indicator
      }
      ... on TrailingPriceBuyStopAlert {
        alertType
        trailingBuyStopType
        trailing
        indicator
      }
      ... on EarningsAlert {
        alertType
        triggerBefore
      }
      ... on DividendsAlert {
        alertType
        triggerBefore
      }
      ... on TimeReviewAlert {
        alertType
        reviewInterval
      }
      ... on MetricsAlert {
        alertType
        indicator
      }
      ... on WatchlistAlert {
        alertType
        watchlistID
      }
      ... on ChecklistAlert {
        alertType
        checklistID
        alertOnFail
        indicator
      }
      ... on ScreenerAlert {
        alertType
        screenerID
        indicator
      }
    }
    group
    tagIDs
    spaceIDs
    displayOrder
    createdAt
    updatedAt
    triggeredCount
    triggeredAt
    lastCheckedAt
  }
}
"""

ADD_ALERT_MUTATION = """
mutation AddAlert($input: AddAlertInput) {
  alerts_addAlert(input: $input) {
    alert {
      id
      enabled
      symbols
      description
      comment
    }
  }
}
"""

UPDATE_ALERT_MUTATION = """
mutation UpdateAlert($update: UpdateAlertInput) {
  alerts_updateAlert(update: $update) {
    alert {
      id
      enabled
      symbols
      description
      comment
    }
  }
}
"""

DELETE_ALERT_MUTATION = """
mutation DeleteAlert($id: String!) {
  alerts_deleteAlert(id: $id)
}
"""

GET_ALERT_TAGS_QUERY = """
query GetAlertTags($name: String) {
  alerts_alertTags(name: $name) {
    alertTags {
      id
      userID
      name
      color
    }
    returnedCount
    totalPossibleCount
  }
}
"""


class AlertsClient:
    """Client for the ``alerts_*`` GraphQL namespace."""

    def __init__(self, transport: GraphqlClient | None = None) -> None:
        """Initialize the client with an optional GraphQL transport override."""
        self.transport = transport or GraphqlClient()

    async def get_alerts(
        self,
        *,
        bearer_token: str,
        comment: str | None = None,
        symbols: list[str] | None = None,
        tag_ids: list[str] | None = None,
        space_ids: list[str] | None = None,
        hide_watchlist_alerts: bool = True,
    ) -> dict[str, Any]:
        """Return alerts for the authenticated user."""
        variables = {
            "input": {
                "comment": comment or "",
                "symbols": symbols,
                "tagIDs": tag_ids,
                "spaceIDs": space_ids,
                "hide_watchlist_alerts": hide_watchlist_alerts,
            }
        }
        return await self.transport.execute(GET_ALERTS_QUERY, variables=variables, bearer_token=bearer_token)

    async def get_alert(self, *, bearer_token: str, alert_id: str) -> dict[str, Any]:
        """Return one alert by ID for the authenticated user."""
        return await self.transport.execute(GET_ALERT_QUERY, variables={"alertID": alert_id}, bearer_token=bearer_token)

    async def add_alert(
        self,
        *,
        bearer_token: str,
        alert_type: str,
        symbols: list[str],
        repeated: bool,
        expire_at: str | None = None,
        comment: str | None = None,
        notification_types: list[str] | None = None,
        info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Add a new alert for the authenticated user."""
        variables = {
            "input": {
                "alertType": alert_type,
                "symbols": symbols,
                "repeated": repeated,
                "expireAt": expire_at,
                "comment": comment,
                "notificationTypes": notification_types,
                "info": info,
            }
        }
        return await self.transport.execute(ADD_ALERT_MUTATION, variables=variables, bearer_token=bearer_token)

    async def update_alert(
        self,
        *,
        bearer_token: str,
        alert_id: str,
        enabled: bool,
        symbols: list[str] | None = None,
        repeated: bool | None = None,
        expire_at: str | None = None,
        comment: str | None = None,
        notification_types: list[str] | None = None,
        info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update an existing alert for the authenticated user."""
        variables = {
            "update": {
                "id": alert_id,
                "enabled": enabled,
                "symbols": symbols,
                "repeated": repeated,
                "expireAt": expire_at,
                "comment": comment,
                "notificationTypes": notification_types,
                "info": info,
            }
        }
        return await self.transport.execute(UPDATE_ALERT_MUTATION, variables=variables, bearer_token=bearer_token)

    async def delete_alert(self, *, bearer_token: str, alert_id: str) -> bool:
        """Delete an alert for the authenticated user."""
        data = await self.transport.execute(DELETE_ALERT_MUTATION, variables={"id": alert_id}, bearer_token=bearer_token)
        return bool(data.get("alerts_deleteAlert", False))

    async def get_alert_tags(self, *, bearer_token: str, name: str | None = None) -> dict[str, Any]:
        """Return alert tags for the authenticated user."""
        return await self.transport.execute(GET_ALERT_TAGS_QUERY, variables={"name": name}, bearer_token=bearer_token)


def normalise_alert(raw: dict[str, Any]) -> dict[str, Any]:
    """Return the bridge-friendly alert record shape."""
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


async def fetch_alerts(bearer_token: str, *, client: GraphqlClient | None = None) -> list[dict[str, Any]]:
    """Fetch alerts in the shape expected by the memory bridge."""
    data = await AlertsClient(transport=client).get_alerts(bearer_token=bearer_token)
    raw = (data.get("alerts_alerts") or {}).get("alerts") or []
    return [normalise_alert(alert) for alert in raw if isinstance(alert, dict)]
