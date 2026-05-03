"""Tests for Phase 19: autonomous skill review hook and runner."""

from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import make_dataclass, replace
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai.config import hook_config
from ai.hooks.base import load_hook_config
from ai.hooks.runner import _DEFAULT_HOOKS
from ai.hooks.types import HookContext
from ai.hooks.skill_review import SkillReviewHook, _count_tool_calls
from ai.memory.para import MemoryPathError, ParaMemoryLayout
from ai.skills.review_runner import ReviewRunner

# ─── helpers ──────────────────────────────────────────────────────────────────


def _msg(role: str, name: str | None = None, content: str = "") -> dict[str, Any]:
    return {"role": role, "name": name, "content": content}


def _tool_msgs(n: int) -> list[dict[str, Any]]:
    return [_msg("tool", name=f"tool_{i}") for i in range(n)]


def _make_ctx(
    messages: list[Any],
    threshold: int = 5,
    user_id: str = "u1",
    conv_id: str = "c1",
    skill_review_model: str = "deepseek/deepseek-v4-pro",
) -> HookContext:
    cfg = replace(
        hook_config,
        AI_SKILL_REVIEW_THRESHOLD=threshold,
        AI_SKILL_REVIEW_MODEL=skill_review_model,
    )
    return HookContext(
        user_id=user_id,
        conversation_id=conv_id,
        user_message="test query",
        response_text="test response",
        request=None,
        messages=messages,
        config=cfg,
        turn_index=1,
    )


# ─── _count_tool_calls ────────────────────────────────────────────────────────


def test_count_tool_calls_empty():
    assert _count_tool_calls([]) == 0


def test_count_tool_calls_all_tool():
    msgs = _tool_msgs(5)
    assert _count_tool_calls(msgs) == 5


def test_count_tool_calls_mixed_roles():
    msgs = [_msg("user"), _msg("assistant"), _msg("tool"), _msg("tool")]
    assert _count_tool_calls(msgs) == 2


def test_count_tool_calls_provider_message_objects():
    """Works with objects that have a .role attribute (e.g. ProviderMessage)."""
    Msg = make_dataclass("Msg", [("role", str), ("name", str | None), ("content", str)])
    msgs = [
        Msg(role="user", name=None, content="q"),
        Msg(role="tool", name="t1", content="r"),
    ]
    assert _count_tool_calls(msgs) == 1


# ─── SkillReviewHook — below threshold ────────────────────────────────────────


def test_below_threshold_returns_ok_skipped():
    hook = SkillReviewHook(threshold=5)
    ctx = _make_ctx(_tool_msgs(3))
    result = hook.run(ctx)
    assert result.ok
    assert result.detail == "below_threshold"
    assert result.data["tool_count"] == 3


def test_exactly_at_threshold_triggers():
    """At or above threshold → review_dispatched (with a fake runner)."""
    runner = MagicMock()
    runner.run = AsyncMock(return_value=Path("/tmp/proposed.md"))
    hook = SkillReviewHook(runner=runner, threshold=5)
    ctx = _make_ctx(_tool_msgs(5))
    result = hook.run(ctx)
    assert result.ok
    assert result.detail == "review_dispatched"


def test_above_threshold_triggers():
    runner = MagicMock()
    runner.run = AsyncMock(return_value=Path("/tmp/proposed.md"))
    hook = SkillReviewHook(runner=runner, threshold=5)
    ctx = _make_ctx(_tool_msgs(10))
    result = hook.run(ctx)
    assert result.ok
    assert result.detail == "review_dispatched"


# ─── SkillReviewHook — disabled ───────────────────────────────────────────────


def test_threshold_zero_disables():
    hook = SkillReviewHook(threshold=0)
    ctx = _make_ctx(_tool_msgs(100))
    result = hook.run(ctx)
    assert result.ok
    assert result.detail == "disabled"


# ─── dedupe: two calls don't spawn two tasks ──────────────────────────────────


def test_second_call_returns_already_pending():
    runner = MagicMock()

    async def _slow_run(**kwargs):
        await asyncio.sleep(0.1)
        return Path("/tmp/proposed.md")

    runner.run = _slow_run
    hook = SkillReviewHook(runner=runner, threshold=5)
    ctx = _make_ctx(_tool_msgs(5))

    first = hook.run(ctx)
    second = hook.run(ctx)

    assert first.detail == "review_dispatched"
    assert second.detail == "already_pending"


def test_different_sessions_independent():
    runner = MagicMock()

    async def _fast_run(**kwargs):
        return Path("/tmp/proposed.md")

    runner.run = _fast_run
    hook = SkillReviewHook(runner=runner, threshold=3)
    ctx_a = _make_ctx(_tool_msgs(3), user_id="alice", conv_id="c1")
    ctx_b = _make_ctx(_tool_msgs(3), user_id="bob", conv_id="c2")

    res_a = hook.run(ctx_a)
    res_b = hook.run(ctx_b)
    assert res_a.detail == "review_dispatched"
    assert res_b.detail == "review_dispatched"


def test_hook_passes_configured_skill_review_model(monkeypatch):
    captured: dict[str, Any] = {}
    runner = MagicMock()

    async def _run(**kwargs):
        captured.update(kwargs)
        return Path("/tmp/proposed.md")

    class ImmediateThread:
        def __init__(self, *, target, args=(), kwargs=None, **_ignored):
            self._target = target
            self._args = args
            self._kwargs = kwargs or {}

        def start(self):
            self._target(*self._args, **self._kwargs)

    runner.run = _run
    monkeypatch.setattr("ai.hooks.skill_review.threading.Thread", ImmediateThread)

    hook = SkillReviewHook(runner=runner, threshold=3)
    ctx = _make_ctx(_tool_msgs(3), skill_review_model="deepseek/deepseek-v4-pro")
    result = hook.run(ctx)

    assert result.detail == "review_dispatched"
    assert captured["skill_review_model"] == "deepseek/deepseek-v4-pro"


# ─── ReviewRunner ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_review_runner_writes_file(tmp_path):
    layout = ParaMemoryLayout(memory_root=tmp_path)

    async def _fake_llm(prompt: str) -> str:
        return "## My Proposed Skill\n\nname: my-skill\ndescription: Does X"

    runner = ReviewRunner(layout=layout, call_llm=_fake_llm)
    out = await runner.run(
        user_id="u1",
        user_message="what is AAPL PE ratio?",
        response_text="The PE is 28",
        messages=_tool_msgs(3),
        skill_review_model="deepseek/deepseek-v4-pro",
    )

    assert out.exists()
    assert out.parent.name == "skill_review_queue"
    text = out.read_text()
    assert "status: pending_review" in text
    assert "proposed_for_user: u1" in text
    assert "source: autonomous_skill_review" in text
    assert "My Proposed Skill" in text
    assert "my-skill" in text


@pytest.mark.asyncio
async def test_review_runner_uses_llm_call(tmp_path):
    layout = ParaMemoryLayout(memory_root=tmp_path)
    llm_body = "## My Proposed Skill\n\nname: my-skill\ndescription: Does X"
    captured_prompt = ""

    async def _fake_llm(prompt: str) -> str:
        nonlocal captured_prompt
        captured_prompt = prompt
        return llm_body

    runner = ReviewRunner(layout=layout, call_llm=_fake_llm)
    out = await runner.run(
        user_id="u1",
        user_message="analyse sector",
        response_text="Sector overview...",
        messages=_tool_msgs(2),
    )

    text = out.read_text()
    assert "My Proposed Skill" in text
    assert "my-skill" in text
    assert "Assistant response summary: Sector overview" in captured_prompt


@pytest.mark.asyncio
async def test_review_runner_path_jail(tmp_path):
    """Path traversal in user_id must raise MemoryPathError."""
    layout = ParaMemoryLayout(memory_root=tmp_path)
    runner = ReviewRunner(layout=layout)
    with pytest.raises((MemoryPathError, ValueError)):
        await runner.run(
            user_id="../../../etc",
            user_message="escape",
            response_text="",
            messages=[],
        )


@pytest.mark.asyncio
async def test_review_runner_llm_failure_writes_nothing(tmp_path):
    layout = ParaMemoryLayout(memory_root=tmp_path)

    async def _broken_llm(prompt: str) -> str:
        raise RuntimeError("LLM unavailable")

    runner = ReviewRunner(layout=layout, call_llm=_broken_llm)
    with pytest.raises(RuntimeError, match="LLM unavailable"):
        await runner.run(
            user_id="u1",
            user_message="q",
            response_text="r",
            messages=_tool_msgs(2),
        )

    assert list(tmp_path.rglob("proposed-*.md")) == []


@pytest.mark.asyncio
async def test_review_runner_empty_llm_output_writes_nothing(tmp_path):
    layout = ParaMemoryLayout(memory_root=tmp_path)

    async def _empty_llm(prompt: str) -> str:
        return " \n "

    runner = ReviewRunner(layout=layout, call_llm=_empty_llm)
    with pytest.raises(ValueError, match="empty output"):
        await runner.run(
            user_id="u1",
            user_message="q",
            response_text="r",
            messages=_tool_msgs(2),
        )

    assert list(tmp_path.rglob("proposed-*.md")) == []


# ─── runner.py registration ───────────────────────────────────────────────────


def test_skill_review_registered_in_default_hooks():
    assert "skill_review" in _DEFAULT_HOOKS
    assert isinstance(_DEFAULT_HOOKS["skill_review"], SkillReviewHook)
    assert "extract_memories" in _DEFAULT_HOOKS


# ─── HookConfig env-backed threshold ─────────────────────────────────────────
def test_load_hook_config_reads_threshold(monkeypatch):
    monkeypatch.setenv("AI_SKILL_REVIEW_THRESHOLD", "25")

    cfg = load_hook_config()
    assert cfg.AI_SKILL_REVIEW_THRESHOLD == 25


def test_load_hook_config_reads_skill_review_model(monkeypatch):
    monkeypatch.setenv("AI_SKILL_REVIEW_MODEL", "openai/gpt-5-mini")

    cfg = load_hook_config()
    assert cfg.AI_SKILL_REVIEW_MODEL == "openai/gpt-5-mini"


def test_load_hook_config_default_threshold():
    os.environ.pop("AI_SKILL_REVIEW_THRESHOLD", None)
    cfg = load_hook_config()
    assert cfg.AI_SKILL_REVIEW_THRESHOLD == 10


def test_load_hook_config_default_skill_review_model():
    os.environ.pop("AI_SKILL_REVIEW_MODEL", None)
    cfg = load_hook_config()
    assert cfg.AI_SKILL_REVIEW_MODEL == "deepseek/deepseek-v4-pro"
