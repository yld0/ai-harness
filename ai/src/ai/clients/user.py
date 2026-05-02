"""Typed client for the authenticated-user GraphQL surface."""

from __future__ import annotations

from typing import Any

from ai.clients.transport import GraphqlClient

ME_QUERY = """
query AuthMe {
  auth_me {
    id
    isSuperuser
  }
}
"""


class UserClient:
    """Client for authenticated user metadata."""

    def __init__(self, transport: GraphqlClient | None = None) -> None:
        """Initialize the client with an optional GraphQL transport override."""
        self.transport = transport or GraphqlClient()

    async def fetch_me(self, bearer_token: str) -> dict[str, Any]:
        """Return the authenticated user's profile."""
        data = await self.transport.execute(ME_QUERY, bearer_token=bearer_token)
        return data.get("auth_me") or {}
