"""Tests for Phase 11 slash command system.

Covers:
- Parser: simple tokens, quoted args, multi-word, no-command text
- Registry: registration, lookup, unknown commands
- Handlers: /compact, /dream, /skill list, /skill view, /personality
- Runner integration: structured slash_command, text-prefix detection,
  unknown command pass-through, /personality side_effects
"""

from __future__ import annotations

import pytest
from pathlib import Path

from ai.commands.parser import parse_slash_command
from ai.commands.base import CommandResult, get_handler, register_builtins


@pytest.fixture(autouse=True)
def _register_builtin_commands():
    """Ensure built-in handlers are registered (runner normally does this)."""
    register_builtins(replace=True)


# ──────────────────────────── Parser ─────────────────────────────────────── #


class TestParseSlashCommand:
    def test_no_slash_returns_none(self):
        assert parse_slash_command("hello world") is None

    def test_empty_returns_none(self):
        assert parse_slash_command("") is None

    def test_lone_slash_returns_none(self):
        assert parse_slash_command("/") is None

    def test_simple_command(self):
        r = parse_slash_command("/compact")
        assert r is not None
        assert r.name == "compact"
        assert r.args == []

    def test_command_with_args(self):
        r = parse_slash_command("/skill list")
        assert r is not None
        assert r.name == "skill"
        assert r.args == ["list"]

    def test_multiple_args(self):
        r = parse_slash_command("/skill view myskill")
        assert r is not None
        assert r.name == "skill"
        assert r.args == ["view", "myskill"]

    def test_quoted_arg(self):
        r = parse_slash_command('/skill view "my skill name"')
        assert r is not None
        assert r.args == ["view", "my skill name"]

    def test_single_quoted_arg(self):
        r = parse_slash_command("/personality 'code reviewer'")
        assert r is not None
        assert r.args == ["code reviewer"]

    def test_remainder_text_after_newline(self):
        r = parse_slash_command("/compact\nsome extra text")
        assert r is not None
        assert r.name == "compact"
        assert r.remainder == "some extra text"

    def test_case_insensitive_name(self):
        r = parse_slash_command("/SKILL list")
        assert r is not None
        assert r.name == "skill"

    def test_raw_preserves_first_line(self):
        r = parse_slash_command('/skill view "name"')
        assert r is not None
        assert r.raw == '/skill view "name"'

    def test_unmatched_quote_falls_back(self):
        # shlex failure: should not raise, splits on whitespace instead
        r = parse_slash_command('/skill view unclosed"')
        assert r is not None
        assert r.name == "skill"

    def test_whitespace_prefix_stripped(self):
        r = parse_slash_command("   /dream  ")
        assert r is not None
        assert r.name == "dream"


# ──────────────────────────── Registry ───────────────────────────────────── #


class TestRegistry:
    def test_builtin_handlers_registered(self):
        for cmd in ("compact", "dream", "skill", "personality"):
            assert get_handler(cmd) is not None, f"handler for /{cmd} not registered"

    def test_alias_lookup(self):
        assert get_handler("skills") is not None  # alias for skill
        assert get_handler("persona") is not None  # alias for personality

    def test_unknown_returns_none(self):
        assert get_handler("definitely_not_a_command") is None

    def test_lookup_case_insensitive(self):
        assert get_handler("COMPACT") is not None


# ──────────────────────────── Handler: /compact ───────────────────────────── #


@pytest.mark.asyncio
async def test_compact_handler():

    handler = get_handler("compact")
    result = await handler.handle([], context={})
    assert isinstance(result, CommandResult)
    assert result.dispatched is True
    assert result.side_effects.get("trigger_hook") == "compact"
    assert "compact" in result.text.lower()


# ──────────────────────────── Handler: /dream ─────────────────────────────── #


@pytest.mark.asyncio
async def test_dream_handler():

    handler = get_handler("dream")
    result = await handler.handle([], context={})
    assert result.dispatched is True
    assert result.side_effects.get("trigger_hook") == "auto_dream"
    assert "dream" in result.text.lower()


# ──────────────────────────── Handler: /skill ─────────────────────────────── #


@pytest.mark.asyncio
async def test_skill_list(tmp_path):

    handler = get_handler("skill")
    # Empty repo root → "No skills" message
    result = await handler.handle(["list"], context={"repo_root": tmp_path})
    assert isinstance(result, CommandResult)
    assert result.dispatched is True


@pytest.mark.asyncio
async def test_skill_unknown_subcommand(tmp_path):

    handler = get_handler("skill")
    result = await handler.handle(["badcmd"], context={"repo_root": tmp_path})
    assert "Usage" in result.text


@pytest.mark.asyncio
async def test_skill_view_unknown(tmp_path):

    handler = get_handler("skill")
    result = await handler.handle(["view", "nonexistent"], context={"repo_root": tmp_path})
    assert "Unknown skill" in result.text or "nonexistent" in result.text


# ──────────────────────────── Handler: /personality ──────────────────────── #


@pytest.mark.asyncio
async def test_personality_list(tmp_path):
    """List discovers personalities from repo root if present."""

    handler = get_handler("personality")
    # Use tmp_path as repo_root — no personalities/ subdir → empty list
    result = await handler.handle(["list"], context={"repo_root": tmp_path})
    assert isinstance(result, CommandResult)
    assert result.dispatched is True


@pytest.mark.asyncio
async def test_personality_set_known(tmp_path):
    """Setting a known personality stores name in side_effects."""

    # Create a personalities dir under tmp_path with one file
    pers_dir = tmp_path / "personalities"
    pers_dir.mkdir()
    (pers_dir / "testpersona.md").write_text("---\nname: testpersona\ndescription: A test personality.\n---\n\nBe brief.")
    handler = get_handler("personality")
    result = await handler.handle(["testpersona"], context={"repo_root": tmp_path})
    assert result.error is None
    assert result.side_effects.get("personality") == "testpersona"
    assert "testpersona" in result.text


@pytest.mark.asyncio
async def test_personality_unknown_fails_soft(tmp_path):
    """Unknown personality returns user-visible message with error set."""

    handler = get_handler("personality")
    result = await handler.handle(["ghost"], context={"repo_root": tmp_path})
    assert result.error == "personality_not_found"
    assert "ghost" in result.text


# ──────────────────────────── Runner integration ─────────────────────────── #


@pytest.mark.asyncio
async def test_runner_dispatches_structured_slash_command():
    """Structured slash_command field triggers handler, not LLM."""
    from ai.agent.runner import AgentRunner
    from ai.schemas.agent import AgentChatRequest

    runner = AgentRunner()
    req = AgentChatRequest.model_validate(
        {
            "conversationID": "conv-sc-1",
            "request": {"query": "ignored"},
            "context": {"route": "chats", "routeMetadata": {}},
            "slash_command": {"name": "compact", "args": []},
        }
    )
    turn = await runner.run_chat_turn(req, user_id="u1")
    assert turn.response.metadata.get("slash_command") == "compact"
    assert turn.response.metadata.get("runner") == "phase-11"


@pytest.mark.asyncio
async def test_runner_detects_slash_in_text():
    """/compact in query text is parsed and dispatched."""
    from ai.agent.runner import AgentRunner
    from ai.schemas.agent import AgentChatRequest

    runner = AgentRunner()
    req = AgentChatRequest.model_validate(
        {
            "conversationID": "conv-sc-2",
            "request": {"query": "/compact"},
            "context": {"route": "chats", "routeMetadata": {}},
        }
    )
    turn = await runner.run_chat_turn(req, user_id="u2")
    assert turn.response.metadata.get("slash_command") == "compact"


@pytest.mark.asyncio
async def test_runner_unknown_command_passes_through_to_llm():
    """Unknown slash command falls through to normal LLM processing."""
    from ai.agent.runner import AgentRunner
    from ai.schemas.agent import AgentChatRequest

    runner = AgentRunner()
    req = AgentChatRequest.model_validate(
        {
            "conversationID": "conv-sc-3",
            "request": {"query": "/unknownxyz do something"},
            "context": {"route": "chats", "routeMetadata": {}},
        }
    )
    turn = await runner.run_chat_turn(req, user_id="u3")
    # LLM path: unknown command passes through with metadata marker
    assert turn.response.metadata.get("slash_command_passthrough") == "unknownxyz"


@pytest.mark.asyncio
async def test_runner_personality_side_effect(tmp_path):
    """/personality <name> side_effects carry personality name in turn metadata."""
    from ai.commands.base import get_handler

    # Seed a personality file under tmp_path/personalities/
    pers_dir = tmp_path / "personalities"
    pers_dir.mkdir()
    (pers_dir / "analyst.md").write_text("---\nname: analyst\ndescription: Financial analyst voice.\n---\n\nBe analytical.")

    handler = get_handler("personality")
    result = await handler.handle(["analyst"], context={"repo_root": tmp_path})
    assert result.side_effects.get("personality") == "analyst"
