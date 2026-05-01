"""Smoke tests for the standalone CLI (Phase 16).

Uses subprocess so the cold-start path is exercised with no FastAPI import.
All LLM calls use DEV_ECHO_MODE=echo for determinism.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import os as _os

_PYTHON = sys.executable
_SRC = str(Path(__file__).parent.parent / "src")
_BASE_ENV = {
    # Inherit parent so PATH, HOME, SSL_CERT_FILE etc. are present
    **_os.environ,
    "PYTHONPATH": _SRC,
    "DEV_ECHO_MODE": "true",
    # Suppress optional heavy-dep warnings
    "PYTHONWARNINGS": "ignore",
}


def _run(*args: str, extra_env: dict | None = None, **kw) -> subprocess.CompletedProcess:
    env = {**_BASE_ENV, **(extra_env or {})}
    return subprocess.run(
        [_PYTHON, "-m", "ai.cli", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        **kw,
    )


# ─── --once single-shot ───────────────────────────────────────────────────────


# TODO: Re-enable this test when we have a way to test the CLI without a database
# def test_chat_once_exits_zero():
#     result = _run("chat", "--once", "What is AAPL PE?")
#     assert result.returncode == 0, result.stderr


# def test_chat_once_prints_to_stdout():
#     result = _run("chat", "--once", "Hello world")
#     assert result.returncode == 0, result.stderr
#     assert result.stdout.strip() != ""


# def test_chat_once_response_contains_text():
#     result = _run("chat", "--once", "ping")
#     assert result.returncode == 0, result.stderr
#     # EchoProvider echoes the user message back
#     assert "ping" in result.stdout.lower() or len(result.stdout.strip()) > 0


# def test_chat_once_with_user_id():
#     result = _run("chat", "--once", "hi", "--user-id", "test-user")
#     assert result.returncode == 0, result.stderr


# def test_chat_once_with_mode_explain():
#     result = _run("chat", "--once", "Explain recursion", "--mode", "explain")
#     assert result.returncode == 0, result.stderr


# def test_chat_once_with_mode_plan():
#     result = _run("chat", "--once", "Plan a refactor", "--mode", "plan")
#     assert result.returncode == 0, result.stderr


# def test_chat_once_verbose_prints_to_stderr():
#     result = _run("chat", "--once", "hi", "--verbose")
#     assert result.returncode == 0, result.stderr
#     # verbose prints user/mode line to stderr
#     assert "user" in result.stderr.lower() or "mode" in result.stderr.lower() or result.returncode == 0


# def test_chat_once_empty_query_exits_nonzero():
#     result = _run("chat", "--once", "")
#     assert result.returncode != 0


def test_chat_once_does_not_import_fastapi():
    """Cold-start must not pull in FastAPI."""
    result = subprocess.run(
        [
            _PYTHON,
            "-c",
            (
                "import sys; sys.path.insert(0, {src!r})\n"
                "import importlib, types\n"
                "_real = importlib.import_module\n"
                "imported = []\n"
                "def _tracking(name, *a, **kw):\n"
                "    imported.append(name)\n"
                "    return _real(name, *a, **kw)\n"
                "import builtins\n"
                "sys.modules.get  # just verify interpreter ok\n"
                "from ai.cli.chat import _build_parser, _build_request\n"
                "assert 'fastapi' not in sys.modules, 'fastapi imported on cold start'\n"
                "print('ok')\n"
            ).format(src=_SRC),
        ],
        capture_output=True,
        text=True,
        env={**_BASE_ENV},
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


# ─── --help ───────────────────────────────────────────────────────────────────


def test_chat_help_exits_zero():
    result = _run("chat", "--help")
    # argparse --help exits 0
    assert result.returncode == 0


def test_top_level_help_exits_zero():
    result = _run("--help")
    assert result.returncode == 0


# ─── CliProgressSink unit tests (in-process) ─────────────────────────────────

import io
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_cli_progress_sink_verbose_prints_cot():
    from ai.cli.chat import CliProgressSink

    sink = CliProgressSink(verbose=True)
    buf = io.StringIO()
    with patch("sys.stderr", buf):
        await sink.emit("cot_step", {"step_type": "thinking", "label": "Pondering…"})
    assert "thinking" in buf.getvalue()
    assert "Pondering" in buf.getvalue()


@pytest.mark.asyncio
async def test_cli_progress_sink_silent_when_not_verbose():
    from ai.cli.chat import CliProgressSink

    sink = CliProgressSink(verbose=False)
    buf = io.StringIO()
    with patch("sys.stderr", buf):
        await sink.emit("cot_step", {"step_type": "thinking", "label": "Pondering…"})
    assert buf.getvalue() == ""


@pytest.mark.asyncio
async def test_cli_progress_sink_task_progress():
    from ai.cli.chat import CliProgressSink

    sink = CliProgressSink(verbose=True)
    buf = io.StringIO()
    with patch("sys.stderr", buf):
        await sink.emit(
            "task_progress",
            {"title": "Running…", "items": [{"type": "item", "content": "step 1"}]},
        )
    assert "Running" in buf.getvalue()
    assert "step 1" in buf.getvalue()


@pytest.mark.asyncio
async def test_cli_progress_sink_usage():
    from ai.cli.chat import CliProgressSink

    sink = CliProgressSink(verbose=True)
    buf = io.StringIO()
    with patch("sys.stderr", buf):
        await sink.emit("usage", {"total_tokens": 42, "model": "echo"})
    assert "42" in buf.getvalue()
    assert "echo" in buf.getvalue()


@pytest.mark.asyncio
async def test_cli_progress_sink_unknown_event_silent():
    from ai.cli.chat import CliProgressSink

    sink = CliProgressSink(verbose=True)
    buf = io.StringIO()
    with patch("sys.stderr", buf):
        await sink.emit("conversation_id", {"conversation_id": "abc"})
    assert buf.getvalue() == ""


# ─── Config resolution ────────────────────────────────────────────────────────


def test_resolve_config_defaults():
    import types
    from ai.cli.config import resolve_config

    args = types.SimpleNamespace(
        user_id=None,
        api_key=None,
        memory_root=None,
        model=None,
        mode="auto",
        route=None,
        verbose=False,
        env_file=None,
    )
    cfg = resolve_config(args)
    assert cfg.user_id == "cli-user"
    assert cfg.mode == "auto"
    assert cfg.verbose is False


def test_resolve_config_cli_args_take_precedence(monkeypatch):
    import types
    from ai.cli.config import resolve_config

    monkeypatch.setenv("CLI_USER_ID", "env-user")
    args = types.SimpleNamespace(
        user_id="cli-user-override",
        api_key="tok",
        memory_root=None,
        model="gpt-4o",
        mode="plan",
        route=None,
        verbose=True,
        env_file=None,
    )
    cfg = resolve_config(args)
    assert cfg.user_id == "cli-user-override"
    assert cfg.model == "gpt-4o"
    assert cfg.mode == "plan"
    assert cfg.bearer_token == "tok"
    assert cfg.verbose is True


def test_resolve_config_env_fallback(monkeypatch):
    import types
    from ai.cli.config import resolve_config

    monkeypatch.setenv("CLI_USER_ID", "from-env")
    monkeypatch.setenv("YLD_JWT", "jwt-tok")
    args = types.SimpleNamespace(
        user_id=None,
        api_key=None,
        memory_root=None,
        model=None,
        mode="auto",
        route=None,
        verbose=False,
        env_file=None,
    )
    cfg = resolve_config(args)
    assert cfg.user_id == "from-env"
    assert cfg.bearer_token == "jwt-tok"
