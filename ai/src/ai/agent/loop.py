"""Bounded provider/tool loop used by the AgentRunner."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol

from ai.agent.progress import NoopProgressSink, ProgressSink
from ai.utils.spinner_verbs import choose_spinner_verb_bucket

if TYPE_CHECKING:
    from ai.tools.types import ToolContext

MAX_ITERATIONS = 24
FinishReason = Literal["stop", "tool_calls", "length", "error"]
ToolHandler = Callable[..., Awaitable[Any] | Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderMessage:
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderTurn:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LoopResult:
    text: str
    messages: list[ProviderMessage]
    iterations: int
    finish_reason: FinishReason
    metadata: dict[str, Any] = field(default_factory=dict)


class Provider(Protocol):
    async def complete(self, messages: list[ProviderMessage], *, tools_enabled: bool, effort: str) -> ProviderTurn: ...


class ToolRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, name: str, handler: ToolHandler) -> None:
        self._handlers[name] = handler

    def has_tool(self, name: str) -> bool:
        return name in self._handlers

    async def execute(self, call: ToolCall, ctx: ToolContext) -> str:
        handler = self._handlers.get(call.name)
        if handler is None:
            return json.dumps(
                {
                    "ok": False,
                    "error": {"code": "tool_not_found", "message": call.name},
                },
                sort_keys=True,
            )
        try:
            value = handler(ctx, call.arguments)
            if hasattr(value, "__await__"):
                value = await value  # type: ignore[assignment]
            if isinstance(value, str):
                return value
            return json.dumps({"ok": True, "result": value}, sort_keys=True, default=str)
        except Exception as exc:
            return json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "tool_error",
                        "message": f"{type(exc).__name__}: {exc}",
                    },
                },
                sort_keys=True,
            )


def normalize_finish_reason(raw: str | None, *, has_tool_calls: bool = False) -> FinishReason:
    value = (raw or "").lower()
    if has_tool_calls or value in {"tool_calls", "function_call", "requires_action"}:
        return "tool_calls"
    if value in {"stop", "end_turn", "complete", "completed", "done"}:
        return "stop"
    if value in {"length", "max_tokens", "max_output_tokens"}:
        return "length"
    return "error" if value else "stop"


async def run_turn_loop(
    *,
    provider: Provider,
    messages: list[ProviderMessage],
    tool_ctx: ToolContext,
    tools: ToolRegistry | None = None,
    tools_enabled: bool = True,
    effort: str = "low",
    progress: ProgressSink | None = None,
    max_iterations: int = MAX_ITERATIONS,
) -> LoopResult:
    registry = tools or ToolRegistry()
    sink = progress or NoopProgressSink()
    working_messages = list(messages)
    last_turn = ProviderTurn(content="", finish_reason="stop")

    _spinner_ctx: str | None = " ".join(filter(None, [tool_ctx.route or None, effort])) or None

    for iteration in range(1, max_iterations + 1):
        await sink.cot_step(
            step_id=f"llm-{iteration}",
            step_type="thinking",
            title=f"LLM iteration {iteration}",
            status="active",
            label=choose_spinner_verb_bucket(_spinner_ctx),
        )
        last_turn = await provider.complete(
            working_messages,
            tools_enabled=tools_enabled,
            effort=effort,
        )
        finish_reason = normalize_finish_reason(last_turn.finish_reason, has_tool_calls=bool(last_turn.tool_calls))
        working_messages.append(
            ProviderMessage(
                role="assistant",
                content=last_turn.content,
                tool_calls=last_turn.tool_calls,
            )
        )
        await sink.cot_step(
            step_id=f"llm-{iteration}",
            step_type="thinking",
            title=f"LLM iteration {iteration}",
            status="complete",
        )

        if finish_reason != "tool_calls" or not tools_enabled:
            return LoopResult(
                text=last_turn.content,
                messages=working_messages,
                iterations=iteration,
                finish_reason=finish_reason,
                metadata=last_turn.metadata,
            )

        for call in last_turn.tool_calls:
            # tool_start / tool_done are emitted by each Tool implementation (Phase 6).
            result = await registry.execute(call, tool_ctx)
            working_messages.append(
                ProviderMessage(
                    role="tool",
                    content=result,
                    name=call.name,
                    tool_call_id=call.id,
                )
            )

    return LoopResult(
        text=last_turn.content,
        messages=working_messages,
        iterations=max_iterations,
        finish_reason="length",
        metadata={**last_turn.metadata, "max_iterations": max_iterations},
    )
