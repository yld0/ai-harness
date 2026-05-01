"""Post-response hooks: compact vs collapse, isolation (Phase 7)."""

from __future__ import annotations

import asyncio

from ai.agent.loop import ProviderMessage
from ai.hooks.base import HookConfig, HookContext, HookResult, build_hook_context
from ai.hooks.compact import compact_messages
from ai.hooks.collapse import collapse_messages
from ai.hooks.runner import HookRunner


def _system_user_assistant_user_assistant() -> list[ProviderMessage]:
    return [
        ProviderMessage(role="system", content="SYS" * 100),
        ProviderMessage(role="user", content="u1"),
        ProviderMessage(role="assistant", content="a1"),
        ProviderMessage(role="user", content="u2"),
        ProviderMessage(role="assistant", content="a2"),
    ]


def test_compact_reduces_middle_and_keeps_endpoints() -> None:
    msgs = _system_user_assistant_user_assistant()
    out = compact_messages(msgs, soft_threshold=10, summarizer=lambda m: "SUM")
    assert len(out) == 3
    assert out[0].role == "system"
    assert out[1].role == "assistant" and "SUM" in out[1].content
    assert out[2].role == "assistant"
    assert out[2].content == "a2"


def test_collapse_keeps_system_and_recent_window() -> None:
    msgs = _system_user_assistant_user_assistant()
    out = collapse_messages(msgs, hard_threshold=10, keep_recent_pairs=1)
    assert out[0].role == "system"
    assert out[0].content.startswith("SYS")
    assert len(out) == 3
    assert out[-1].content == "a2"


def test_hook_exception_does_not_abort_sequence() -> None:
    class Boom:
        name: str = "boom"

        def run(self, ctx: HookContext) -> HookResult:
            raise RuntimeError("boom")

    class Fine:
        name: str = "fine"

        def run(self, ctx: HookContext) -> HookResult:
            return HookResult(name="fine", ok=True)

    cfg = HookConfig(hooks_enabled=["boom", "fine"], post_hook_timeout_s=5.0)
    runner = HookRunner(config=cfg, hooks={"boom": Boom(), "fine": Fine()})
    ctx = build_hook_context(
        user_id="u1",
        conversation_id="c1",
        user_message="hi",
        response_text="ok",
        request=object(),
        messages=[],
        turn_index=1,
    )

    async def go() -> None:
        res = await runner.run_after_response(ctx)
        assert len(res) == 2
        assert res[0].name == "boom"
        assert res[0].ok is False
        assert "RuntimeError" in (res[0].detail or "")
        assert res[1].ok is True

    asyncio.run(go())
