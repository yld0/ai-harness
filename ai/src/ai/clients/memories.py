"""Typed client for the ``memories_*`` GraphQL surface (Neo4j)."""

from __future__ import annotations

import logging
from typing import Any

from ai.clients.transport import GraphqlClient

logger = logging.getLogger(__name__)

MEMORIES_QUERY = """
query GetMemories {
  memories_memories {
    memories {
      memoryID
      memory
      createdAt
      updatedAt
    }
    returnedCount
  }
}
"""


def _normalise_memory(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "memory_id": raw.get("memoryID"),
        "memory": str(raw.get("memory") or "").strip(),
        "created_at": str(raw.get("createdAt") or ""),
        "updated_at": str(raw.get("updatedAt") or ""),
    }


class MemoriesClient:
    """Client for the ``memories_*`` GraphQL namespace."""

    def __init__(self, client: GraphqlClient | None = None) -> None:
        self._gql = client or GraphqlClient()

    async def fetch_memories(self, bearer_token: str) -> list[dict[str, Any]]:
        """Fetch all memories and return normalised records."""
        data = await self._gql.execute(MEMORIES_QUERY, bearer_token=bearer_token)
        raw: list[dict] = (data.get("memories_memories") or {}).get("memories") or []
        return [_normalise_memory(r) for r in raw if isinstance(r, dict)]


async def fetch_memories(
    bearer_token: str,
    *,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    """Convenience wrapper matching the module-level signature used by the bridge."""
    return await MemoriesClient(client=client).fetch_memories(bearer_token)
