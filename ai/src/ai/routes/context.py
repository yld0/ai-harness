"""Shared RouteContext and RouteResult types for Phase 14 route handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from ai.agent.progress import ProgressSink
from ai.memory.para import ParaMemoryLayout
from ai.memory.writer import MemoryWriter
from ai.schemas.agent import AgentChatRequest


@dataclass
class RouteResult:
    """Structured result returned by every route handler.

    *text*     — human-readable response text (may be Markdown).
    *metadata* — extra structured data merged into the response metadata.
    *ok*       — False signals a handled error; the runner wraps it with an
                 error key but still returns a 200 response (fail-soft).
    *error*    — short error code set when *ok* is False.
    """

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    ok: bool = True
    error: Optional[str] = None


@dataclass
class RouteContext:
    """Everything a route handler needs.

    Handlers must not import ``AgentRunner`` directly — use ``call_llm``
    for any LLM work, which delegates through the runner without creating a
    circular import.
    """

    user_id: str
    request: AgentChatRequest
    bearer_token: Optional[str]
    input: dict[str, Any]
    layout: ParaMemoryLayout
    writer: MemoryWriter
    progress: ProgressSink
    # Delegates one LLM turn; returns the assistant text.
    call_llm: Callable[[str], Awaitable[str]]
