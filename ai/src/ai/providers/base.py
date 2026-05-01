"""Provider-facing request/response contracts."""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from ai.agent.loop import ProviderMessage, ToolCall

ProviderName = Literal["gemini", "openrouter"]
ProviderEffort = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class ProviderRequest:
    messages: list[ProviderMessage]
    model: str
    effort: ProviderEffort = "low"
    tools: list[dict[str, Any]] = field(default_factory=list)
    response_format: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    request_thinking: bool = False


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    provider: ProviderName | str = "gemini"
    raw_ref: str | None = None
    finish_reason: str = "stop"
    thinking_text: str | None = None
    model: str | None = None


class ProviderClient(Protocol):
    name: ProviderName

    async def generate(self, request: ProviderRequest) -> ProviderResponse: ...
