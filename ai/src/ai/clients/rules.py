"""Typed client for the ``rules_*`` GraphQL surface.

Fetches always-apply and manual rules concurrently, returning a typed
``RulesSnapshot``.  Follows the same pattern as ``AIClient`` — wraps the
low-level ``GraphqlClient`` transport with named, typed methods.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from ai.rules.models import Rule, RulesSnapshot
from ai.clients.transport import GraphqlClient

logger = logging.getLogger(__name__)

ALWAYS_APPLY_QUERY = """
query AlwaysApplyRules {
  rules_alwaysApplyRules {
    rules {
      id
      name
      instructions
      alwaysApply
    }
  }
}
"""

MANUAL_RULES_QUERY = """
query ManualRules {
  rules_rules(filter: { alwaysApply: false }) {
    rules {
      id
      name
      instructions
      alwaysApply
    }
  }
}
"""


def _parse_rule(raw: dict[str, Any]) -> Rule:
    return Rule(
        id=str(raw.get("id", "")),
        name=raw.get("name") or None,
        instructions=str(raw.get("instructions", "")),
        always_apply=bool(raw.get("alwaysApply", False)),
    )


def _extract_rules(data: Any, key: str) -> list[Rule]:
    if not isinstance(data, dict):
        return []
    raw_list = (data.get(key) or {}).get("rules") or []
    result = []
    for item in raw_list:
        if isinstance(item, dict):
            try:
                result.append(_parse_rule(item))
            except Exception as exc:  # noqa: BLE001
                logger.warning("failed to parse rule %r: %s", item, exc)
    return result


class RulesClient:
    """Client for the ``rules_*`` GraphQL namespace."""

    def __init__(self, client: GraphqlClient | None = None) -> None:
        self._gql = client or GraphqlClient()

    async def fetch_rules_snapshot(
        self,
        bearer_token: str,
    ) -> RulesSnapshot:
        """Fetch always-apply and manual rules concurrently.

        Returns an empty ``RulesSnapshot`` on any network or parse error.
        """
        always_result, manual_result = await asyncio.gather(
            self._gql.execute(ALWAYS_APPLY_QUERY, bearer_token=bearer_token),
            self._gql.execute(MANUAL_RULES_QUERY, bearer_token=bearer_token),
            return_exceptions=True,
        )

        always_rules = _extract_rules(
            always_result if not isinstance(always_result, BaseException) else {},
            "rules_alwaysApplyRules",
        )
        manual_rules = _extract_rules(
            manual_result if not isinstance(manual_result, BaseException) else {},
            "rules_rules",
        )

        if isinstance(always_result, BaseException):
            logger.warning("always-apply rules fetch failed: %s", always_result)
        if isinstance(manual_result, BaseException):
            logger.warning("manual rules fetch failed: %s", manual_result)

        return RulesSnapshot(
            always_apply=always_rules,
            manual=manual_rules,
            fetched_at=datetime.now(timezone.utc),
        )


# ── Module-level convenience function (preserves existing call-site API) ─── #


async def fetch_rules_snapshot(
    bearer_token: str,
    *,
    client: Any | None = None,
) -> RulesSnapshot:
    """Convenience wrapper matching the original module-level signature.

    Accepts an optional ``GraphqlClient`` override (for tests).
    """
    rules_client = RulesClient(client=client)
    return await rules_client.fetch_rules_snapshot(bearer_token)
