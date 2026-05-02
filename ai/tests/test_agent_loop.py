import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from ai.agent.loop import (
    ProviderMessage,
    ProviderTurn,
    ToolCall,
    ToolRegistry,
    run_turn_loop,
)
from ai.agent.progress import NoopProgressSink
from ai.tools.types import ToolContext
from ai.const import SPINNER_VERBS

_DEFAULT_CTX = ToolContext(
    user_id="test",
    session_id="test",
    session_permission="ReadOnly",
    channel="web",
    route="",
    progress=NoopProgressSink(),
    bearer_token=None,
    memory_root=Path("/tmp"),
    project_root=Path("."),
)


class ToolThenFinalProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, messages: list[ProviderMessage], *, tools_enabled: bool, effort: str) -> ProviderTurn:
        self.calls += 1
        if self.calls == 1:
            assert tools_enabled is True
            assert effort == "medium"
            return ProviderTurn(
                content="Need a tool",
                tool_calls=[ToolCall(id="call-1", name="lookup", arguments={"ticker": "AAPL"})],
                finish_reason="tool_calls",
            )
        tool_result = next(message.content for message in messages if message.role == "tool")
        return ProviderTurn(content=f"Final with {tool_result}", finish_reason="stop")


def test_loop_executes_tool_then_returns_final_text() -> None:
    async def run() -> None:
        tools = ToolRegistry()
        tools.register("lookup", lambda ctx, args: {"ticker": args["ticker"], "price": 123})
        result = await run_turn_loop(
            provider=ToolThenFinalProvider(),
            messages=[ProviderMessage(role="user", content="price?")],
            tool_ctx=_DEFAULT_CTX,
            tools=tools,
            tools_enabled=True,
            effort="medium",
        )

        assert result.finish_reason == "stop"
        assert result.iterations == 2
        assert '"price": 123' in result.text
        assert [message.role for message in result.messages] == [
            "user",
            "assistant",
            "tool",
            "assistant",
        ]

    asyncio.run(run())


def test_loop_stops_at_max_iterations() -> None:
    class AlwaysToolProvider:
        async def complete(self, messages: list[ProviderMessage], *, tools_enabled: bool, effort: str) -> ProviderTurn:
            return ProviderTurn(
                content="again",
                tool_calls=[ToolCall(id=f"call-{len(messages)}", name="missing")],
                finish_reason="tool_calls",
            )

    async def run() -> None:
        result = await run_turn_loop(
            provider=AlwaysToolProvider(),
            messages=[ProviderMessage(role="user", content="loop")],
            tool_ctx=_DEFAULT_CTX,
            max_iterations=2,
        )

        assert result.finish_reason == "length"
        assert result.iterations == 2

    asyncio.run(run())


# ── spinner verbs ──────────────────────────────────────────────────────────────


def test_spinner_verbs_list_nonempty() -> None:
    """``SPINNER_VERBS`` contains a healthy number of entries."""
    assert len(SPINNER_VERBS) >= 20


# def test_loop_active_thinking_step_has_label() -> None:
#     """ The active 'thinking' cot_step fired before each LLM call carries a label. """
#     from ai.agent.progress import CollectingProgressSink

#     class SingleTurnProvider:
#         async def complete(self, messages: list[ProviderMessage], *, tools_enabled: bool, effort: str) -> ProviderTurn:
#             return ProviderTurn(content="done", finish_reason="stop")

#     async def run() -> None:
#         sink = CollectingProgressSink()
#         with patch(
#             "ai.utils.spinner_verbs.choose_spinner_verb",
#             new_callable=AsyncMock,
#             return_value="Cogitating…",
#         ):
#             await run_turn_loop(
#                 provider=SingleTurnProvider(),
#                 messages=[ProviderMessage(role="user", content="hi")],
#                 progress=sink,
#             )
#         active_thinking = [
#             e
#             for e in sink.events
#             if e.get("type") == "cot_step"
#             and (e.get("payload") or {}).get("step_type") == "thinking"
#             and (e.get("payload") or {}).get("status") == "active"
#         ]
#         assert active_thinking, "expected at least one active thinking cot_step"
#         label = active_thinking[0]["payload"].get("label") or ""
#         assert label.endswith("…"), f"label {label!r} should end with ellipsis"
#         verb = label.rstrip("…")
#         assert verb in SPINNER_VERBS

#     asyncio.run(run())
