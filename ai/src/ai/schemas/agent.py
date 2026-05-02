from typing import Any, Dict, List, Literal, Optional, TYPE_CHECKING, Union
from enum import Enum

from pydantic import AliasChoices, Field, field_validator, model_validator

from ai.agent.modes import AgentMode
from ai.schemas._base import CamelBaseModel
from ai.schemas.graph.chats import GraphChatRequestInput, GraphChatResponseInput


class CacheStyle(str, Enum):
    """Cache style for cache + litellm proxy cache."""

    NORMAL = "normal"
    SEMANTIC = "semantic"


class CacheMode(str, Enum):
    """Cache mode."""

    NORMAL = "normal"
    NO_STORE = "no_store"
    NO_CACHE = "no_cache"


class CacheOptions(CamelBaseModel):
    cache_type: CacheStyle = Field(
        default=CacheStyle.NORMAL,
        description="The type of cache to use. Normal will cache the response based on the query, semantic will cache the response based on the semantic meaning of the query. ",
    )
    mode: CacheMode = Field(
        default=CacheMode.NORMAL,
        description="The mode of cache to use. Normal will cache the response based on the query, no_store will not cache the response, no_cache will force a fresh response, bypassing the cache.",
    )


class TimeFrame(Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    ALL = "all"


class ReasoningType(Enum):
    NONE = "none"
    DISABLE = "disable"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class OutputFormat(str, Enum):
    """Output format for the chat response."""

    AUTO = "auto"
    TABLE = "table"
    CHART = "chart"
    DATA = "data"
    INFOGRAPHIC = "infographic"
    SLIDES = "slides"
    VIDEO = "video"
    REPORT = "report"


class UIComponent(str, Enum):
    """UI component for the chat response."""

    AUTO = "auto"
    TABLE = "table"
    CHART = "chart"
    ARTICLE = "article"
    PROVIDER_TABS = "provider_tabs"
    PROVIDER_RANKINGS = "provider_rankings"
    AGGREGATE_RANKINGS = "aggregate_rankings"


#  UI Components
# ===============================


class ChartData(CamelBaseModel):
    labels: List[str]
    datasets: List[dict]


class ChatTableComponent(CamelBaseModel):
    type: UIComponent = UIComponent.TABLE
    title: str
    headers: List[str]
    rows: List[dict[str, Any]] = Field(default_factory=list, description="The actual data records for the current page.")
    total_records: Optional[int] = Field(default=None, description="The total number of records available across all pages.")


class UIChartType(str, Enum):
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    DOUGHNUT = "doughnut"
    RADAR = "radar"
    AREA = "area"


class ChatChartComponent(CamelBaseModel):
    type: UIComponent = UIComponent.CHART
    source: Optional[str] = Field(description="Optional source of the data for the chart. This could be a link to a source or a description of the source.")
    title: str
    chart_type: UIChartType
    data: ChartData


class ProviderTab(CamelBaseModel):
    model: str
    response: str = Field(description="The content for the provider tab.", default="")


class ChatProviderTabsComponent(CamelBaseModel):
    type: UIComponent = UIComponent.PROVIDER_TABS
    providers: List[ProviderTab] = Field(default_factory=list, description="The list of providers to display in the tabs.")
    default_open: bool = Field(default=False, description="Whether the provider tabs should be open by default.")


class ProviderRanking(CamelBaseModel):
    model: str
    ranking: str = Field(description="The ranking for the provider.", default="")
    parsed_ranking: List[str] = Field(default_factory=list, description="The list of parsed ranking items.")


class ChatProviderRankingsComponent(CamelBaseModel):
    type: UIComponent = UIComponent.PROVIDER_RANKINGS
    rankings: List[ProviderRanking] = Field(default_factory=list, description="The list of rankings to display in the rankings component.")
    default_open: bool = Field(default=False, description="Whether the provider rankings should be open by default.")


class AggregateRanking(CamelBaseModel):
    model: str
    average_rank: float = Field(description="The average rank for the model.", default=0.0)
    rankings_count: int = Field(description="The number of rankings for the model.", default=0)


class ChatAggregateRankingsComponent(CamelBaseModel):
    type: UIComponent = UIComponent.AGGREGATE_RANKINGS
    rankings: List[AggregateRanking] = Field(default_factory=list, description="The list of rankings to display in the rankings component.")
    default_open: bool = Field(default=False, description="Whether the provider rankings should be open by default.")


class ChatCouncilComponent(CamelBaseModel):
    """Council stage data for GraphQL persistence (stage1, stage2, stage3, metadata)."""

    type: Literal["council"] = "council"
    title: str
    data: Dict[str, Any] = Field(default_factory=dict, description="stage1, stage2, stage3, metadata")


# ============================================================================
# Sources
# ============================================================================


class DocumentMetadata(CamelBaseModel):
    id: str
    title: str
    url: str
    source: str
    author: str
    published_date: str
    excerpt: str
    page_number: str
    document_metadata: dict
    fiscal_year: str
    fiscal_quarter: str


class UISourceComponent(str, Enum):
    DOCUMENT_SOURCE = "document_source"
    WEBSITE_SOURCE = "website_source"
    NEWS_SOURCE = "news_source"
    TWITTER_SOURCE = "twitter_source"
    YOUTUBE_SOURCE = "youtube_source"


class WebsiteSourceComponent(CamelBaseModel):
    type: UIComponent = UISourceComponent.WEBSITE_SOURCE
    url: str
    title: str
    description: str


class NewsSourceComponent(CamelBaseModel):
    type: UIComponent = UISourceComponent.NEWS_SOURCE
    url: str
    title: str
    description: str
    image_url: str
    source: str
    author: str
    published_date: str


class TwitterSourceComponent(CamelBaseModel):
    type: UIComponent = UISourceComponent.TWITTER_SOURCE
    url: str
    title: str
    description: str
    image_url: str
    source: str
    author: str
    published_date: str


class YoutubeSourceComponent(CamelBaseModel):
    type: UIComponent = UISourceComponent.YOUTUBE_SOURCE
    url: str
    title: str
    description: str
    image_url: str
    source: str
    author: str
    published_date: str


class DocumentSourceComponent(CamelBaseModel):
    type: UIComponent = UISourceComponent.DOCUMENT_SOURCE
    page_number: str
    excerpt: str
    document_metadata: DocumentMetadata


# ============================================================================
# V3 additions: FileComponent
# ============================================================================


class FileComponent(CamelBaseModel):
    type: Literal["file"] = "file"
    path: Optional[str] = None
    title: str
    mime: Optional[str] = None
    content: Optional[str] = None
    ref_id: Optional[str] = None

    @model_validator(mode="after")
    def require_content_or_ref(self) -> "FileComponent":
        if self.content is None and self.ref_id is None:
            raise ValueError("FileComponent requires either content or ref_id")
        return self


ChatComponent = Union[ChatTableComponent, ChatChartComponent, FileComponent]
ExtraChatComponent = Union[ChatComponent, ChatProviderTabsComponent, ChatProviderRankingsComponent, ChatAggregateRankingsComponent]

SourceComponent = Union[DocumentSourceComponent, WebsiteSourceComponent, NewsSourceComponent, TwitterSourceComponent, YoutubeSourceComponent]


class CouncilStageItem(CamelBaseModel):
    model: str
    response: str


class CouncilRankingItem(CamelBaseModel):
    model: str
    ranking: str
    parsed_ranking: List[str] = Field(default_factory=list, description="The list of parsed ranking items.")


class CouncilResponse(CamelBaseModel):
    stage1: List[CouncilStageItem] = Field(default_factory=list, description="The list of council stage 1 items.")
    stage2: List[CouncilRankingItem] = Field(default_factory=list, description="The list of council stage 2 items.")
    stage3: CouncilStageItem = Field(default=None, description="The council stage 3 item.")


class CouncilRunResult(CamelBaseModel):
    """Version-agnostic council run output. Produced by ai.council.runner.run_council."""

    version: Literal["v1", "v2"]
    stage1: List[CouncilStageItem] = Field(default_factory=list)
    stage2: List[CouncilRankingItem] = Field(default_factory=list)
    stage3: Optional[CouncilStageItem] = Field(default=None, description="Chairman synthesis; None if synthesis failed.")
    aggregate_rankings: List[AggregateRanking] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatContext(CamelBaseModel):
    """
    LLM and agent context.
    """

    route: Optional[
        Literal[
            "chats",
            "spaces",
            "spaces-discover",
            "spaces-knowledge-base-sources-refresh",
            "spaces-summary",
            "spaces-compact",
            "spaces-youtube-summary",
            "nuno",
            "actions-catchup",
            "actions-market-catchup",
            "actions-tldr-news",
            "actions-recent-earnings",
            "llm_council",
        ]
    ] = Field(
        default=None,
        description="The workflow route you are interested in.",
    )
    route_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Specific metadata for the workflow route that is specific to the route.",
    )
    agent: Optional[str] = Field(
        default=None,
        description="The id of the agent you would like to use for the chat request.",
    )
    companies: Optional[List[str]] = Field(
        default=None,
        description="The companies you are interested in. It is the company names you are interested in e.g. Apple, Microsoft, Google, etc.",
    )
    stocks: Optional[List[str]] = Field(
        default=None,
        description="The stock symbols you are interested in.",
    )
    mutual_funds: Optional[List[str]] = Field(
        default=None,
        description="The mutual fund symbols you are interested in.",
    )
    etfs: Optional[List[str]] = Field(
        default=None,
        description="The etf symbols you are interested in.",
    )
    thirteenfs: Optional[List[str]] = Field(
        default=None,
        description="The thirteenf symbols you are interested in.",
    )
    superinvestors: Optional[List[str]] = Field(
        default=None,
        description="The superinvestor symbols you are interested in.",
    )
    exchanges: Optional[List[str]] = Field(
        default=None,
        description="The exchanges you are interested in.",
    )
    regions: Optional[List[str]] = Field(
        default=None,
        description="The regions you are interested in.",
    )
    countries: Optional[List[str]] = Field(
        default=None,
        description="The countries you are interested in.",
    )
    sectors: Optional[List[str]] = Field(
        default=None,
        description="The sectors you are interested in.",
    )
    industries: Optional[List[str]] = Field(
        default=None,
        description="The industries you are interested in.",
    )
    metrics: Optional[List[str]] = Field(
        default=None,
        description="The metrics you are interested in.",
    )
    time_frame: Optional[str] = Field(
        default=None,
        description="The time frame are interested in analyzing the data for.",
    )
    alerts: Optional[List[str]] = Field(
        default=None,
        description="The alert ids you are interested in.",
    )
    watchlists: Optional[List[str]] = Field(
        default=None,
        description="The watchlist ids you are interested in.",
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump(by_alias=True, exclude_none=True)


class LLMRequest(CamelBaseModel):
    query: str


class LLMResponse(CamelBaseModel):
    response: str


class ChatRequest(CamelBaseModel):
    query: str
    cache_mode: Optional[CacheMode] = Field(
        default=CacheMode.NORMAL,
        description="The cache mode to use for the chat request. If not provided, the cache mode will be determined by the agent or user settings.",
    )
    model: Optional[str] = Field(
        default=None,
        description="The model override for the chat request. If not provided, the model will be determined by the agent or user settings.",
    )
    response_format: Optional[OutputFormat] = Field(
        default=OutputFormat.AUTO,
        description="The output format to use for the chat request. If not provided, the output format will be determined by the agent or user settings.",
    )
    reasoning: Optional[ReasoningType] = Field(
        default=ReasoningType.NONE,
        description="The reasoning type to use for the chat request. If not provided, the reasoning will be determined by the agent or user settings.",
    )
    deep_research: Optional[bool] = Field(
        default=False,
        description="Whether to perform deep research for the chat request. If not provided, the deep research will be determined by the agent or user settings.",
    )

    def to_graph(self) -> GraphChatRequestInput:
        """Convert to graphql compatible input model."""
        return GraphChatRequestInput(
            query=self.query,
            model=self.model,
            style=None,
            cache_options=None,
            web_search=True,
            deep_research=(self.deep_research if self.deep_research is not None else False),
        )


class LLMChatResponse(CamelBaseModel):
    """Schema for LLM structured output. Used in response_json_schema for model generation.
    Sources are populated from grounding metadata in post-processing, not from LLM output."""

    text: str = Field(
        description="The llm output text response.",
    )
    thinking: Optional[str] = Field(
        default=None,
        description="The thinking and reasoning text by the LLM.",
    )
    components: List[ChatComponent] = Field(
        default_factory=list,
        description="UI component or source to display along with the text in the chat response.",
    )

    @field_validator("components", mode="before")
    @classmethod
    def components_none_to_empty(cls, v):
        return v if v is not None else []


class ChatResponse(LLMChatResponse):
    """Full chat response. Extends LLMChatResponse with sources (from grounding) and showcase (post-processing)."""

    model: Optional[str] = Field(
        default=None,
        description="The model that generated the response.",
    )
    sources: Optional[List[SourceComponent]] = Field(
        default_factory=list,
        description="Sources from grounding metadata (Google Search). Populated in post-processing.",
    )
    extra_components: Optional[List[ExtraChatComponent]] = Field(
        default_factory=list,
        description="Extra UI components or sources to display along with the text in the chat response.",
    )
    showcase: Optional[List[ChatComponent]] = Field(
        default_factory=list,
        description="Specific ui components we want to display on the right side panel 'showcase' of the chat response.",
    )

    def _component_to_input(self, component: ChatComponent) -> dict:
        """Convert ChatComponent to ChatComponentInput dict."""
        if isinstance(component, ChatTableComponent):
            return {
                "type": component.type.value,
                "title": component.title,
                "content": None,
                "data": {
                    "headers": component.headers,
                    "rows": component.rows,
                },
                "metadata": None,
            }
        elif isinstance(component, ChatChartComponent):
            return {
                "type": component.type.value,
                "title": component.title,
                "content": None,
                "data": component.data.model_dump(by_alias=True),
                "metadata": ({"chartType": component.chart_type.value} if component.chart_type else None),
            }
        elif isinstance(component, ChatCouncilComponent):
            return {
                "type": "council",
                "title": component.title,
                "content": None,
                "data": component.data,
                "metadata": None,
            }
        elif isinstance(component, FileComponent):
            return {
                "type": "file",
                "title": component.title,
                "content": component.content,
                "data": {"path": component.path, "mime": component.mime, "refId": component.ref_id},
                "metadata": None,
            }
        else:
            return {
                "type": "unknown",
                "title": None,
                "content": None,
                "data": None,
                "metadata": None,
            }

    def _extra_component_to_input(self, component: ExtraChatComponent) -> dict:
        """Convert ExtraChatComponent to ChatComponentInput dict."""
        if isinstance(component, (ChatTableComponent, ChatChartComponent, ChatCouncilComponent, FileComponent)):
            return self._component_to_input(component)
        if isinstance(component, ChatProviderTabsComponent):
            return {
                "type": component.type.value,
                "title": None,
                "content": None,
                "data": {"providers": [p.model_dump(by_alias=True) for p in component.providers]},
                "metadata": {"defaultOpen": component.default_open},
            }
        if isinstance(component, ChatProviderRankingsComponent):
            return {
                "type": component.type.value,
                "title": None,
                "content": None,
                "data": {"rankings": [r.model_dump(by_alias=True) for r in component.rankings]},
                "metadata": {"defaultOpen": component.default_open},
            }
        if isinstance(component, ChatAggregateRankingsComponent):
            return {
                "type": component.type.value,
                "title": None,
                "content": None,
                "data": {"rankings": [r.model_dump(by_alias=True) for r in component.rankings]},
                "metadata": {"defaultOpen": component.default_open},
            }
        return {
            "type": "unknown",
            "title": None,
            "content": None,
            "data": None,
            "metadata": None,
        }

    def _showcase_to_input(self, showcase: ChatComponent) -> dict:
        """Convert showcase item to ShowcaseItemInput dict."""
        if isinstance(showcase, ChatTableComponent):
            return {
                "type": showcase.type.value,
                "title": showcase.title,
                "description": None,
                "url": None,
                "imageUrl": None,
                "metadata": {"headers": showcase.headers, "rows": showcase.rows},
            }
        elif isinstance(showcase, ChatChartComponent):
            return {
                "type": showcase.type.value,
                "title": showcase.title,
                "description": None,
                "url": None,
                "imageUrl": None,
                "metadata": {
                    "chartType": (showcase.chart_type.value if showcase.chart_type else None),
                    "data": (showcase.data.model_dump(by_alias=True) if showcase.data else None),
                },
            }
        elif isinstance(showcase, ChatProviderTabsComponent):
            return {
                "type": showcase.type.value,
            }
        else:
            return {
                "type": "unknown",
                "title": "",
                "description": None,
                "url": None,
                "imageUrl": None,
                "metadata": None,
            }

    def to_graph(self) -> GraphChatResponseInput:
        """Convert to graphql compatible input model."""
        components = [self._component_to_input(c) for c in self.components]
        if self.extra_components:
            components.extend(self._extra_component_to_input(c) for c in self.extra_components)
        return GraphChatResponseInput(
            reasoning=self.thinking,
            text=self.text,
            components=components,
            showcase=[self._showcase_to_input(s) for s in self.showcase or []],
            metadata={},
        )


# ================================================
# Agent Chat Requests and Responses
# ================================================


class ConfirmationRequest(CamelBaseModel):
    """Request model for confirming a previous action (e.g., delete alert)."""

    conversation_id: str = Field(default="", description="The conversation id for the confirmation request.")
    confirmation: bool = Field(description="Whether the user confirmed the action.")
    reason: Optional[str] = Field(default=None, description="Optional reason for the confirmation decision.")
    alert_id: Optional[str] = Field(default=None, description="ID of the alert to confirm deletion for.")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context about what is being confirmed.")


class SlashCommand(CamelBaseModel):
    name: str
    args: list[str] = Field(default_factory=list)
    raw: Optional[str] = None


class AgentChatRequest(CamelBaseModel):
    conversation_id: str = Field(
        default="", description="The conversation id to use for the chat request. If not provided, a new conversation will be created."
    )
    request: Union[ChatRequest, ConfirmationRequest]
    context: ChatContext
    auto_confirm: Optional[bool] = Field(
        default=False,
        description="If true, automatically confirm actions that normally require confirmation (e.g., delete operations). Use with caution.",
    )
    auto_clarify: Optional[bool] = Field(
        default=False,
        description="If true, automatically clarify the request if needed i.e. LLM makes best judgement. Use with caution.",
    )
    mode: AgentMode = Field(
        default="auto",
        description="Agent behavior mode.",
    )
    slash_command: Optional[SlashCommand] = Field(
        default=None,
        description="Parsed slash command for command-driven requests.",
    )
    automation_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("automationId", "automationID", "automation_id"),
        serialization_alias="automationId",
        description="Automation definition id for short-lived agent runs.",
    )
    automation_run_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("automationRunId", "automationRunID", "automation_run_id"),
        serialization_alias="automationRunId",
        description="Idempotency key for an automation invocation.",
    )
    route: Optional[str] = Field(
        default=None,
        description="V3 run route mirror for /v3/agent/run envelopes.",
    )
    input: Optional[dict[str, Any]] = Field(
        default=None,
        description="Raw route input mirror for /v3/agent/run envelopes.",
    )


#
# Responses
# ================================================
#


class UserConfirmationResponse(CamelBaseModel):
    text: str
    alert_id: Optional[str] = Field(default=None, description="ID of the alert that requires confirmation (for delete operations)")
    watchlist_id: Optional[str] = Field(default=None, description="ID of the watchlist that requires confirmation (for delete operations)")


class UserOption(CamelBaseModel):
    """A single option in a UserOptionsResponse."""

    value: str = Field(description="The value to use when this option is selected")
    label: str = Field(description="The human-readable label for this option")
    description: Optional[str] = Field(default=None, description="Optional description or help text for this option")


class ParameterQuestion(CamelBaseModel):
    """A question for a specific parameter with its options."""

    parameter_name: str = Field(description="The name of the parameter being asked about (e.g., 'alert_type', 'repeated', 'symbol')")
    question: str = Field(description="The question or prompt for this specific parameter")
    options: List[UserOption] = Field(description="List of available options for this parameter")
    parameter_type: Optional[str] = Field(
        default=None, description="Type of parameter: 'enum', 'bool', 'string', 'number', etc. Helps frontend render appropriate UI"
    )


class UserOptionsResponse(CamelBaseModel):
    """Response type for presenting multiple choice options to the user."""

    questions: List[ParameterQuestion] = Field(
        description="List of parameter-specific questions with their options. Each question corresponds to a missing parameter."
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional context about what operation is being performed (e.g., {'operation': 'add_alert'})"
    )


ReplyToUserResponse = Union[ChatResponse, UserConfirmationResponse, UserOptionsResponse]


class AgentChatResponse(CamelBaseModel):
    conversation_id: str
    response: ReplyToUserResponse
    metadata: dict = Field(default_factory=dict, description="The metadata for the chat response. e.g. usage stats, response_time_ms, etc.")


class PartialAgentChatResponse(CamelBaseModel):
    partial: bool = True
    response: ReplyToUserResponse


# ================================================
# Websocket Server Messages (streaming / task updates)
# ================================================


class WsServerMessageType(str, Enum):
    """Discriminator for server→client WebSocket messages."""

    CHAT_RESPONSE = "chat_response"
    TASK_UPDATE = "task_update"
    COT_UPDATE = "cot_update"
    BACKGROUND_TASK_UPDATE = "background_task_update"
    ERROR = "error"


class TaskItemUpdate(CamelBaseModel):
    """Single item for taki-ui Task (TaskItem or TaskItemFile)."""

    type: Literal["item", "file"] = "item"
    content: str = ""


class TaskUpdateMessage(CamelBaseModel):
    """Streaming task progress, maps to taki-ui Task component."""

    task_id: str = Field(description="Correlate updates for same task")
    title: str = Field(description="TaskTrigger title")
    items: List[TaskItemUpdate] = Field(default_factory=list)
    default_open: bool = True


CotStepStatus = Literal["complete", "active", "pending"]


class CotStep(CamelBaseModel):
    """Single chain-of-thought step for taki-ui Chain of Thought."""

    step_id: str = Field(description="Stable id for this step")
    step_type: Literal["search", "get", "synthesize"] = Field(description="Type of step - search or synthesize")
    title: str = Field(description="Step title")
    content: Optional[str] = Field(default=None, description="Optional step body")
    sources: Optional[List[str]] = Field(default_factory=list, description="Sources for the step - documents, etc.")
    websites: Optional[List[str]] = Field(default_factory=list, description="Websites for the step.")
    status: CotStepStatus = Field(description="complete | active | pending")


class ChainOfThoughtUpdate(CamelBaseModel):
    """Incremental chain-of-thought update: one step per message."""

    title: Optional[str] = Field(default=None, description="Title of the chain-of-thought update.")
    steps: List[CotStep] = Field(default_factory=list, description="Steps to append or update by step_id")


BackgroundTaskStepStatus = Literal["complete", "active", "pending"]


class BackgroundTaskStep(CamelBaseModel):
    """Single step for a background task (e.g. compact chats, space summary)."""

    step_id: str = Field(description="Stable id for this step")
    title: str = Field(description="Step title")
    status: BackgroundTaskStepStatus = Field(description="complete | active | pending")


class BackgroundTaskUpdate(CamelBaseModel):
    """Update for a long-running background job (not tied to the active chat)."""

    job_id: str = Field(description="Correlate updates for the same job")
    status: Literal["pending", "active", "complete"] = Field(description="complete | active | pending", default="pending")
    title: str = Field(description="Job title, e.g. 'Compact chats'")
    steps: List[BackgroundTaskStep] = Field(default_factory=list, description="Steps to append or update by step_id")


class ConversationIdUpdate(CamelBaseModel):
    """Sent as soon as a conversation is created/ensured so the client can navigate to /chats2/[id]."""

    conversation_id: str = Field(description="The new or ensured conversation id")


class WsAgentChatResponse(CamelBaseModel):
    type: WsServerMessageType = WsServerMessageType.CHAT_RESPONSE
    data: AgentChatResponse | PartialAgentChatResponse | TaskUpdateMessage | ChainOfThoughtUpdate | BackgroundTaskUpdate | ConversationIdUpdate


# ================================================
# Websocket Authentication Messages
# ================================================


class WsMessageType(str, Enum):
    AUTH_OK = "auth_ok"
    AUTH_ERROR = "auth_error"


class WsAuthRequest(CamelBaseModel):
    """First message from client to authenticate the WebSocket connection."""

    token: str = Field(description="JWT for authentication")


class WsAuthResponse(CamelBaseModel):
    """Server response after successful auth."""

    type: WsMessageType = WsMessageType.AUTH_OK
    message: str = Field(description="Message after successful auth.")


# ================================================
# Websocket Client Request Messages (envelope)
# ================================================


class WsClientMessageType(str, Enum):
    """Discriminator for client→server WebSocket messages (post-auth)."""

    CHAT_REQUEST = "chat_request"
    BACKGROUND_TASK = "background_task"


class BackgroundTaskRequest(CamelBaseModel):
    """Request to start a background job (no conversation_id required)."""

    context: ChatContext


class WsAgentRequest(CamelBaseModel):
    """Client→server WebSocket message envelope (post-auth). Dispatched by type."""

    type: WsClientMessageType = Field(description="Message type: chat_request or background_task.")
    data: Union[AgentChatRequest, BackgroundTaskRequest] = Field(description="Payload; shape depends on type (AgentChatRequest vs BackgroundTaskRequest).")

    @model_validator(mode="before")
    @classmethod
    def validate_data_by_type(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        type_val = raw.get("type")
        data_raw = raw.get("data")
        if data_raw is None:
            return raw
        type_str = type_val.value if isinstance(type_val, WsClientMessageType) else type_val
        if type_str == "chat_request":
            raw["data"] = AgentChatRequest.model_validate(data_raw)
        elif type_str == "background_task":
            raw["data"] = BackgroundTaskRequest.model_validate(data_raw)
        return raw
