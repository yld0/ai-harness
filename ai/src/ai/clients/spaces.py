"""Typed client for the ``spaces_*`` GraphQL surface."""

from __future__ import annotations

import logging
from typing import Any

from ai.clients.transport import GraphqlClient

logger = logging.getLogger(__name__)

GET_SPACE_QUERY = """
query SpacesSpace($id: String!) {
  spaces_space(id: $id) {
    id
    spaceID
    userID
    title
    description
    instructions
    visibility
    image
    model
    agents
    mcpServers
    files
    youtubeChannels
    websites
    includeWebSearch
    suggestedQueries
    dedicatedMemory
    members {
      userID
      role
      joinedAt
      invitedBy
    }
    tagIDs
    inviteCode
    timingValidity
    createdAt
    updatedAt
  }
}
"""

GET_SUMMARIES_QUERY = """
query SpacesSummaries($spaceID: String!, $limit: Int!, $offset: Int!) {
  spaces_summaries(spaceID: $spaceID, limit: $limit, offset: $offset) {
    summaries {
      id
      spaceID
      contentMarkdown
      contentHTML
      tldrMarkdown
      tldrHTML
      keyTakeawaysMarkdown
      keyTakeawaysHTML
      rawContent
      rawContext
      createdAt
    }
    returnedCount
    totalPossibleCount
  }
}
"""

ADD_SUMMARY_MUTATION = """
mutation SpacesAddSummary($input: SpacesAddSummaryInput!) {
  spaces_addSummary(input: $input) {
    id
    spaceID
    contentMarkdown
    contentHTML
    tldrMarkdown
    tldrHTML
    keyTakeawaysMarkdown
    keyTakeawaysHTML
    rawContent
    rawContext
    createdAt
  }
}
"""


class SpacesClient:
    """Client for the ``spaces_*`` GraphQL namespace."""

    def __init__(self, transport: GraphqlClient | None = None) -> None:
        """Initialize the client with an optional GraphQL transport override."""
        self.transport = transport or GraphqlClient()

    async def get_space(self, *, bearer_token: str, space_id: str) -> dict[str, Any] | None:
        """Return one space by ID for the authenticated user."""
        logger.debug("Calling spaces_space for id=%s", space_id)
        data = await self.transport.execute(GET_SPACE_QUERY, variables={"id": space_id}, bearer_token=bearer_token)
        space = data.get("spaces_space")
        return space if isinstance(space, dict) else None

    async def get_summaries(self, *, bearer_token: str, space_id: str, limit: int = 5, offset: int = 0) -> dict[str, Any]:
        """Return LLM summary history for a space."""
        logger.debug("Calling spaces_summaries for spaceID=%s limit=%s offset=%s", space_id, limit, offset)
        data = await self.transport.execute(
            GET_SUMMARIES_QUERY,
            variables={"spaceID": space_id, "limit": limit, "offset": offset},
            bearer_token=bearer_token,
        )
        return data.get("spaces_summaries", {"summaries": [], "returnedCount": 0, "totalPossibleCount": 0})

    async def add_summary(
        self,
        *,
        bearer_token: str,
        space_id: str,
        content: str,
        tldr: str | None = None,
        key_takeaways: str | None = None,
        raw_content: dict[str, Any] | None = None,
        raw_context: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """Add an LLM summary for a space."""
        summary_input: dict[str, Any] = {
            "spaceID": space_id,
            "content": content,
        }
        if tldr is not None:
            summary_input["tldr"] = tldr
        if key_takeaways is not None:
            summary_input["keyTakeaways"] = key_takeaways
        if raw_content is not None:
            summary_input["rawContent"] = raw_content
        if raw_context is not None:
            summary_input["rawContext"] = raw_context
        if timestamp is not None:
            summary_input["timestamp"] = timestamp

        logger.info("Calling spaces_addSummary for spaceID=%s", space_id)
        data = await self.transport.execute(ADD_SUMMARY_MUTATION, variables={"input": summary_input}, bearer_token=bearer_token)
        return data.get("spaces_addSummary", {})
