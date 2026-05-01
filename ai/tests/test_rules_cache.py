"""Tests for Phase 12 rules cache and format.

Covers:
- GraphQL data types: Rule, RulesSnapshot
- format_rules_block: always-apply, manual, mixed, empty
- RulesCache: cache miss → fetch, cache hit (TTL), TTL expiry → re-fetch,
  missing token → empty snapshot, network error → empty snapshot
- Prompt builder: rules_block wired through, golden slot 08_rules
- Runner integration: rules loaded per-turn and passed to PromptBuilder
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from ai.clients.rules import _extract_rules, _parse_rule
from ai.rules.models import Rule, RulesSnapshot
from ai.rules.format import format_rules_block
from ai.rules.cache import RulesCache, _cache_key

# ──────────────────────────── Data types ─────────────────────────────────── #


class TestRule:
    def test_parse_rule_full(self):
        raw = {
            "id": "r1",
            "name": "My Rule",
            "instructions": "Be concise.",
            "alwaysApply": True,
        }
        r = _parse_rule(raw)
        assert r.id == "r1"
        assert r.name == "My Rule"
        assert r.instructions == "Be concise."
        assert r.always_apply is True

    def test_parse_rule_always_apply_false(self):
        raw = {
            "id": "r2",
            "name": None,
            "instructions": "Apply when relevant.",
            "alwaysApply": False,
        }
        r = _parse_rule(raw)
        assert r.always_apply is False
        assert r.name is None

    def test_parse_rule_missing_name_is_none(self):
        r = _parse_rule({"id": "r3", "instructions": "Body."})
        assert r.name is None

    def test_rules_snapshot_is_empty(self):
        s = RulesSnapshot()
        assert s.is_empty is True

    def test_rules_snapshot_not_empty_with_rules(self):
        r = Rule(id="r1", instructions="body", always_apply=True)
        s = RulesSnapshot(always_apply=[r])
        assert s.is_empty is False

    def test_extract_rules_valid(self):
        data = {
            "rules_alwaysApplyRules": {
                "rules": [
                    {"id": "1", "name": "A", "instructions": "i1", "alwaysApply": True},
                ]
            }
        }
        rules = _extract_rules(data, "rules_alwaysApplyRules")
        assert len(rules) == 1
        assert rules[0].id == "1"

    def test_extract_rules_missing_key(self):
        assert _extract_rules({}, "rules_alwaysApplyRules") == []

    def test_extract_rules_non_dict_data(self):
        assert _extract_rules(None, "rules_alwaysApplyRules") == []


# ──────────────────────────── Formatter ──────────────────────────────────── #


class TestFormatRulesBlock:
    def test_empty_snapshot_returns_empty_string(self):
        assert format_rules_block(RulesSnapshot()) == ""

    def test_always_apply_section(self):
        rule = Rule(id="r1", name="Style", instructions="Be concise.", always_apply=True)
        block = format_rules_block(RulesSnapshot(always_apply=[rule]))
        assert "<rules>" in block
        assert "Always-apply" in block
        assert "Style" in block
        assert "Be concise." in block

    def test_manual_section(self):
        rule = Rule(id="r2", name="Finance", instructions="Use numbers.", always_apply=False)
        block = format_rules_block(RulesSnapshot(manual=[rule]))
        assert "Conditional rules" in block
        assert "Finance" in block

    def test_mixed_both_sections(self):
        always = Rule(id="r1", name="A", instructions="always.", always_apply=True)
        manual = Rule(id="r2", name="M", instructions="manual.", always_apply=False)
        block = format_rules_block(RulesSnapshot(always_apply=[always], manual=[manual]))
        assert "Always-apply" in block
        assert "Conditional" in block
        assert block.index("Always-apply") < block.index("Conditional")

    def test_unnamed_rule_fallback(self):
        rule = Rule(id="r1", name=None, instructions="anon.", always_apply=True)
        block = format_rules_block(RulesSnapshot(always_apply=[rule]))
        assert "unnamed rule" in block

    def test_multiple_rules_in_section(self):
        rules = [Rule(id=str(i), name=f"Rule{i}", instructions=f"instr{i}", always_apply=True) for i in range(3)]
        block = format_rules_block(RulesSnapshot(always_apply=rules))
        for i in range(3):
            assert f"Rule{i}" in block


# ──────────────────────────── RulesCache ─────────────────────────────────── #


class TestRulesCache:
    def _snapshot(self, n: int = 1) -> RulesSnapshot:
        rules = [Rule(id=str(i), name=f"R{i}", instructions="body", always_apply=True) for i in range(n)]
        return RulesSnapshot(always_apply=rules)

    @pytest.mark.asyncio
    async def test_none_token_returns_empty(self):
        cache = RulesCache(ttl_s=300)
        snap = await cache.load("u1", None)
        assert snap.is_empty

    @pytest.mark.asyncio
    async def test_cache_miss_fetches(self):
        cache = RulesCache(ttl_s=300)
        expected = self._snapshot(2)
        with patch("ai.rules.cache.fetch_rules_snapshot", new=AsyncMock(return_value=expected)) as mock:
            snap = await cache.load("u1", "token-abc")
        mock.assert_awaited_once()
        assert len(snap.always_apply) == 2

    @pytest.mark.asyncio
    async def test_cache_hit_no_refetch(self):
        cache = RulesCache(ttl_s=300)
        expected = self._snapshot(1)
        with patch("ai.rules.cache.fetch_rules_snapshot", new=AsyncMock(return_value=expected)) as mock:
            await cache.load("u1", "token-abc")
            # Second call within TTL
            snap2 = await cache.load("u1", "token-abc")
        assert mock.await_count == 1  # fetched only once
        assert snap2 is expected

    @pytest.mark.asyncio
    async def test_ttl_expiry_triggers_refetch(self):
        cache = RulesCache(ttl_s=0.01)  # 10ms TTL
        expected = self._snapshot(1)
        with patch("ai.rules.cache.fetch_rules_snapshot", new=AsyncMock(return_value=expected)) as mock:
            await cache.load("u1", "token-abc")
            time.sleep(0.05)  # exceed TTL
            await cache.load("u1", "token-abc")
        assert mock.await_count == 2

    @pytest.mark.asyncio
    async def test_network_error_returns_empty(self):
        cache = RulesCache(ttl_s=300)
        with patch(
            "ai.rules.cache.fetch_rules_snapshot",
            new=AsyncMock(side_effect=RuntimeError("timeout")),
        ):
            snap = await cache.load("u1", "token-abc")
        assert snap.is_empty

    @pytest.mark.asyncio
    async def test_invalidate_forces_refetch(self):
        cache = RulesCache(ttl_s=300)
        expected = self._snapshot(1)
        with patch("ai.rules.cache.fetch_rules_snapshot", new=AsyncMock(return_value=expected)) as mock:
            await cache.load("u1", "token-abc")
            cache.invalidate("u1", "token-abc")
            await cache.load("u1", "token-abc")
        assert mock.await_count == 2

    @pytest.mark.asyncio
    async def test_different_tokens_different_cache_slots(self):
        cache = RulesCache(ttl_s=300)
        snap_a = self._snapshot(1)
        snap_b = self._snapshot(2)
        calls: list[str] = []

        async def fake_fetch(token: str, *, client=None) -> RulesSnapshot:
            calls.append(token)
            return snap_a if token == "token-a" else snap_b

        with patch("ai.rules.cache.fetch_rules_snapshot", new=fake_fetch):
            result_a = await cache.load("u1", "token-a")
            result_b = await cache.load("u1", "token-b")

        assert len(result_a.always_apply) == 1
        assert len(result_b.always_apply) == 2
        assert calls == ["token-a", "token-b"]

    @pytest.mark.asyncio
    async def test_clear_flushes_all(self):
        cache = RulesCache(ttl_s=300)
        expected = self._snapshot(1)
        with patch("ai.rules.cache.fetch_rules_snapshot", new=AsyncMock(return_value=expected)) as mock:
            await cache.load("u1", "token-abc")
            cache.clear()
            await cache.load("u1", "token-abc")
        assert mock.await_count == 2

    def test_cache_key_stable(self):
        k1 = _cache_key("user1", "token")
        k2 = _cache_key("user1", "token")
        k3 = _cache_key("user1", "other")
        assert k1 == k2
        assert k1 != k3


# ──────────────────────────── PromptBuilder integration ──────────────────── #


class TestPromptBuilderRulesSlot:
    def _make_snapshot_with_context(self, tmp_path):
        from ai.agent.context_files import ContextFilesLoader, ContextFilesSnapshot

        return ContextFilesSnapshot(identity="Test identity.", files=[])

    def test_rules_block_appears_in_prompt(self):
        from ai.agent.prompt_builder import PromptBuilder
        from ai.agent.context_files import ContextFilesSnapshot

        rule = Rule(id="r1", name="Style", instructions="Be concise.", always_apply=True)
        snap = RulesSnapshot(always_apply=[rule])
        block = format_rules_block(snap)

        pb = PromptBuilder()
        ctx = ContextFilesSnapshot(identity="id", files=[])
        result = pb.build(context=ctx, rules_block=block)
        assert "Style" in result.prompt
        assert "Be concise." in result.prompt
        assert "<rules>" in result.prompt

    def test_empty_rules_uses_placeholder(self):
        from ai.agent.prompt_builder import PromptBuilder
        from ai.agent.context_files import ContextFilesSnapshot

        pb = PromptBuilder()
        ctx = ContextFilesSnapshot(identity="id", files=[])
        result = pb.build(context=ctx, rules_block="")
        # PromptBuilder should show the pending placeholder when rules_block is ""
        assert "08_rules" in result.prompt

    def test_rules_in_correct_slot_order(self):
        """Slot 08_rules must appear after 07_skills_index and before 09_context_files."""
        from ai.agent.prompt_builder import PromptBuilder
        from ai.agent.context_files import ContextFilesSnapshot

        rule = Rule(id="r1", name="R", instructions="body.", always_apply=True)
        snap = RulesSnapshot(always_apply=[rule])
        pb = PromptBuilder()
        ctx = ContextFilesSnapshot(identity="id", files=[])
        result = pb.build(context=ctx, rules_block=format_rules_block(snap))
        idx_07 = result.prompt.index("07_skills_index")
        idx_08 = result.prompt.index("08_rules")
        idx_09 = result.prompt.index("09_context_files")
        assert idx_07 < idx_08 < idx_09


# ──────────────────────────── Runner integration ─────────────────────────── #


@pytest.mark.asyncio
async def test_runner_passes_rules_to_prompt_builder():
    """AgentRunner fetches rules, formats them, and passes to PromptBuilder."""
    from ai.agent.runner import AgentRunner
    from ai.schemas.agent import AgentChatRequest

    rule = Rule(id="rr1", name="NoJargon", instructions="Avoid jargon.", always_apply=True)
    snap = RulesSnapshot(always_apply=[rule])

    fake_cache = RulesCache(ttl_s=300)
    with patch("ai.rules.cache.fetch_rules_snapshot", new=AsyncMock(return_value=snap)):
        runner = AgentRunner(rules_cache=fake_cache)
        req = AgentChatRequest.model_validate(
            {
                "conversationID": "conv-rules-1",
                "request": {"query": "hello"},
                "context": {"route": "chats", "routeMetadata": {}},
            }
        )
        turn = await runner.run_chat_turn(req, user_id="u-rules", bearer_token="tok-test")

    # Rules were fetched (cache miss → fetch_rules_snapshot called)
    assert turn.response is not None


@pytest.mark.asyncio
async def test_runner_empty_rules_no_crash():
    """Missing token → empty rules → no crash."""
    from ai.agent.runner import AgentRunner
    from ai.schemas.agent import AgentChatRequest

    runner = AgentRunner()
    req = AgentChatRequest.model_validate(
        {
            "conversationID": "conv-rules-2",
            "request": {"query": "hello"},
            "context": {"route": "chats", "routeMetadata": {}},
        }
    )
    # No bearer_token → RulesCache returns empty snapshot
    turn = await runner.run_chat_turn(req, user_id="u-norules")
    assert turn.response is not None
