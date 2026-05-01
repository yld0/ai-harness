"""Typed client for the ``auth_me`` GraphQL field."""

from __future__ import annotations

import logging
from typing import Any

from ai.tools.graphql import GraphqlClient

logger = logging.getLogger(__name__)

AUTH_ME_QUERY = """
query AuthMe {
  auth_me {
    isSuperuser
  }
}
"""


class UserClient:
    """Client for the ``auth_me`` GraphQL field."""

    def __init__(self, client: GraphqlClient | None = None) -> None:
        self._gql = client or GraphqlClient()

    async def fetch_me(self, bearer_token: str) -> dict[str, Any]:
        """Return the ``auth_me`` payload for the bearer token's user."""
        data = await self._gql.execute(AUTH_ME_QUERY, bearer_token=bearer_token)
        raw = data.get("auth_me") or {}
        if not isinstance(raw, dict):
            raise TypeError(f"auth_me payload is not an object: {raw!r}")
        return raw
