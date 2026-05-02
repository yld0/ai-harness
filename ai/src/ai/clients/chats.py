"""Typed client for the ``chats_*`` GraphQL surface."""

from __future__ import annotations

import logging
from typing import Any

from ai.clients.transport import GraphqlClient
from ai.schemas.agent import ChatRequest, ChatResponse
from ai.schemas.graph.chats import AddConversationResponse, AddInteractionResponse, ChatHistoryMessage, InteractionsResponse

logger = logging.getLogger(__name__)

ADD_CONVERSATION_MUTATION = """
mutation AddConversation($input: AddConversationInput!) {
  chats_addConversation(input: $input) {
    conversationID
    title
  }
}
"""

ENSURE_CONVERSATION_MUTATION = """
mutation EnsureConversation($input: EnsureConversationInput!) {
  chats_ensureConversation(input: $input) {
    conversationID
    title
  }
}
"""

ADD_INTERACTION_MUTATION = """
mutation AddInteraction($input: AddInteractionInput!) {
  chats_addInteraction(input: $input) {
    interactionID
  }
}
"""

GET_INTERACTIONS_QUERY = """
query GetInteractions($conversationID: String!, $tree: Boolean, $pagination: PaginationInput) {
  chats_interactions(conversationID: $conversationID, tree: $tree, pagination: $pagination) {
    interactions {
      uuid
      sender
      parentUUID
      partId
      timestamp
      text
      components {
        type
        title
        content
        data
        metadata
      }
      showcase {
        type
        title
        description
        url
        imageUrl
        metadata
      }
      truncated
    }
    totalCount
    hasNextPage
    hasPreviousPage
  }
}
"""

GET_CHAT_HISTORY_QUERY = """
query GetChatHistory($input: MongoSearchInteractionsInput!) {
  chats_interactions(input: $input) {
    interactions {
      uuid
      sender
      parentUUID
      partId
      timestamp
      text
    }
    returnedCount
    totalPossibleCount
  }
}
"""


class ChatsClient:
    """Client for the ``chats_*`` GraphQL namespace."""

    def __init__(self, transport: GraphqlClient | None = None) -> None:
        """Initialize the client with an optional GraphQL transport override."""
        self.transport = transport or GraphqlClient()

    async def add_conversation(
        self,
        *,
        bearer_token: str,
        title: str | None = None,
        space_ids: list[str] | None = None,
        temporary: bool = False,
    ) -> AddConversationResponse:
        """Add a new conversation via GraphQL."""
        variables = {
            "input": {
                "title": title,
                "spaceIDs": space_ids or [],
                "temporary": temporary,
            }
        }
        logger.info("Calling chats_addConversation")
        data = await self.transport.execute(ADD_CONVERSATION_MUTATION, variables=variables, bearer_token=bearer_token)
        return AddConversationResponse(**data.get("chats_addConversation", {}))

    async def ensure_conversation(self, *, bearer_token: str, slot: str) -> AddConversationResponse:
        """Return or create the single authenticated-user conversation for a slot."""
        variables = {"input": {"slot": slot}}
        logger.info("Calling chats_ensureConversation with slot=%s", slot)
        data = await self.transport.execute(ENSURE_CONVERSATION_MUTATION, variables=variables, bearer_token=bearer_token)
        return AddConversationResponse(**data.get("chats_ensureConversation", {}))

    async def add_interaction(
        self,
        *,
        bearer_token: str,
        conversation_id: str,
        request: ChatRequest,
        response: ChatResponse,
    ) -> AddInteractionResponse:
        """Add an interaction to a conversation via GraphQL."""
        request_input = request.to_graph()
        response_input = response.to_graph()
        logger.info("Calling chats_addInteraction with conversation_id=%s", conversation_id)
        variables = {
            "input": {
                "interaction": {
                    "conversationID": conversation_id,
                    "request": request_input.model_dump(by_alias=True),
                    "response": response_input.model_dump(by_alias=True),
                    "truncated": False,
                    "citations": [],
                    "webSearchResults": [],
                }
            }
        }
        data = await self.transport.execute(ADD_INTERACTION_MUTATION, variables=variables, bearer_token=bearer_token)
        return AddInteractionResponse(**data.get("chats_addInteraction", {}))

    async def get_interactions(
        self,
        *,
        bearer_token: str,
        conversation_id: str,
        tree: bool = True,
        limit: int | None = None,
        offset: int | None = None,
    ) -> InteractionsResponse:
        """Return interactions for a conversation via GraphQL."""
        variables: dict[str, Any] = {
            "conversationID": conversation_id,
            "tree": tree,
        }
        pagination: dict[str, int] = {}
        if limit is not None:
            pagination["limit"] = limit
        if offset is not None:
            pagination["offset"] = offset
        if pagination:
            variables["pagination"] = pagination

        logger.info("Calling chats_interactions with conversation_id=%s tree=%s", conversation_id, tree)
        data = await self.transport.execute(GET_INTERACTIONS_QUERY, variables=variables, bearer_token=bearer_token)
        return InteractionsResponse(**data.get("chats_interactions", {}))

    async def get_chat_history(self, *, bearer_token: str, conversation_id: str) -> list[ChatHistoryMessage]:
        """Return simplified chat history messages for a conversation."""
        variables = {
            "input": {
                "conversationID": conversation_id,
                "tree": True,
            }
        }
        logger.info("Calling chats_interactions history with conversation_id=%s", conversation_id)
        data = await self.transport.execute(GET_CHAT_HISTORY_QUERY, variables=variables, bearer_token=bearer_token)
        interactions_data = data.get("chats_interactions", {}).get("interactions", [])
        interactions_data.sort(key=lambda message: message.get("timestamp") or "")
        return [ChatHistoryMessage(**message) for message in interactions_data]
