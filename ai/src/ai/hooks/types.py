"""Hook contracts: post-turn processing after the client has the final response."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from ai.config import HookConfig, hook_config
from ai.schemas.agent import AgentChatRequest


@dataclass
class HookContext:
    """Inputs passed to each post-response hook for one completed turn."""

    user_id: str
    conversation_id: str
    user_message: str
    response_text: str
    request: AgentChatRequest
    messages: list[Any]
    config: HookConfig = field(default_factory=lambda: hook_config)
    turn_index: int = 0


@dataclass
class HookResult:
    """Outcome of a single hook execution."""

    name: str
    ok: bool
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class Hook(Protocol):
    """Stateless post-response hook contract."""

    name: str

    def run(self, ctx: HookContext) -> HookResult: ...
