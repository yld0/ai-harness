"""
GraphQL input and output models for chats/interactions mutations.

These models match the GraphQL schema exactly and are used for GraphQL mutations and responses.
"""

from typing import List, Optional

from pydantic import Field

from ai.schemas._base import CamelBaseModel


class GraphChatRequestInput(CamelBaseModel):
    """Input model for GraphQL chats_addInteraction mutation.

    Matches the GraphQL ChatRequestInput schema exactly.
    Note: history field is excluded as it's not part of the input type.
    """

    query: str
    model: Optional[str] = None
    style: Optional[str] = None
    cache_options: Optional[dict] = Field(default=None, alias="cacheOptions")
    web_search: bool = Field(default=False, alias="webSearch")
    deep_research: bool = Field(default=False, alias="deepResearch")
    symbols: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)
    regions: List[str] = Field(default_factory=list)
    countries: List[str] = Field(default_factory=list)
    exchanges: List[str] = Field(default_factory=list)


class GraphChatResponseInput(CamelBaseModel):
    """Input model for GraphQL chats_addInteraction mutation.

    Matches the GraphQL ChatResponseInput schema exactly.
    """

    reasoning: Optional[str] = None
    text: str
    components: List[dict] = Field(default_factory=list)
    showcase: List[dict] = Field(default_factory=list)
    metadata: Optional[dict] = Field(default_factory=dict)


class CitationInput(CamelBaseModel):
    """Input model for GraphQL CitationInput."""

    part_id: int = Field(alias="partId")
    title: str
    url: str
    position: str
    position_end: Optional[str] = Field(default=None, alias="positionEnd")


class WebSearchResultInput(CamelBaseModel):
    """Input model for GraphQL WebSearchResultInput."""

    title: str
    url: str
    preview: str
    position: str
    position_end: Optional[str] = Field(default=None, alias="positionEnd")


class AddConversationResponse(CamelBaseModel):
    """Response model for GraphQL chats_addConversation mutation."""

    conversation_id: str = Field(alias="conversationID")
    title: str


class AddInteractionResponse(CamelBaseModel):
    """Response model for GraphQL chats_addInteraction mutation."""

    interaction_id: str = Field(alias="interactionID")


class ChatComponent(CamelBaseModel):
    """GraphQL ChatComponent type."""

    type: str
    title: Optional[str] = None
    content: Optional[str] = None
    data: Optional[dict] = None
    metadata: Optional[dict] = None


class ShowcaseItem(CamelBaseModel):
    """GraphQL ShowcaseItem type."""

    type: str
    title: str
    description: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = Field(default=None, alias="imageUrl")
    metadata: Optional[dict] = None


class GraphChatMessage(CamelBaseModel):
    """GraphQL ChatMessage type used in InteractionsResponse."""

    uuid: str
    sender: str
    parent_uuid: Optional[str] = Field(default=None, alias="parentUUID")
    part_id: int = Field(alias="partId")
    timestamp: Optional[str] = None
    text: str
    components: List[ChatComponent] = Field(default_factory=list)
    showcase: List[ShowcaseItem] = Field(default_factory=list)
    truncated: bool = False


class InteractionsResponse(CamelBaseModel):
    """Response model for GraphQL chats_interactions query."""

    interactions: List[GraphChatMessage]
    total_count: int = Field(alias="totalCount")
    has_next_page: bool = Field(alias="hasNextPage")
    has_previous_page: bool = Field(alias="hasPreviousPage")


class ChatHistoryMessage(CamelBaseModel):
    """Simplified chat message for history retrieval."""

    uuid: str
    sender: str
    parent_uuid: Optional[str] = Field(default=None, alias="parentUUID")
    part_id: int = Field(alias="partId")
    timestamp: Optional[str] = None
    text: str
