"""Standalone CLI chat loop — no FastAPI required.

Usage examples:

    # Single-shot (exits 0 on success):
    ai chat --once "What is AAPL PE?"

    # Interactive REPL:
    ai chat

    # With options:
    ai chat --model openai/gpt-4o --mode plan --user-id alice

    # Equivalent: python -m ai.cli.main chat ...

Environment variables (all optional):
    CLI_BEARER_TOKEN — Bearer token forwarded to GraphQL tools.
    CLI_USER_ID      — Default user id (default: cli-user).
    CLI_MEMORY_ROOT  — Root directory for PARA memory files.
    DEV_ECHO_MODE    — Set to True for deterministic offline testing.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any

from ai.agent.runner import AgentRunner
from ai.config import agent_config, cli_config
from ai.schemas.agent import AgentChatRequest, ChatContext, ChatRequest

# ─── Progress sink for CLI ────────────────────────────────────────────────────


class CliProgressSink:
    """Writes CoT / task-progress events to stderr so stdout stays clean."""

    def __init__(self, verbose: bool = False) -> None:
        self._verbose = verbose

    async def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if event_type == "cot_step":
            label = payload.get("label") or payload.get("title") or ""
            step_type = payload.get("step_type", "")
            if label and self._verbose:
                print(f"  [{step_type}] {label}", file=sys.stderr)
        elif event_type == "task_progress" and self._verbose:
            title = payload.get("title", "")
            items = payload.get("items", [])
            if title:
                print(f"  ⟳ {title}", file=sys.stderr)
            for item in items:
                if isinstance(item, dict) and item.get("content"):
                    print(f"    • {item['content']}", file=sys.stderr)
        elif event_type == "usage" and self._verbose:
            total = payload.get("total_tokens")
            model = payload.get("model", "")
            if total:
                print(f"  tokens: {total}  model: {model}", file=sys.stderr)
        # conversation_id, task_progress_summary etc. — silently ignored

    async def cot_step(
        self,
        *,
        step_id: str,
        step_type: str,
        title: str,
        status: str = "complete",
        content: str | None = None,
        tool: str | None = None,
        label: str | None = None,
    ) -> None:
        if self._verbose:
            text = label or title
            print(f"  [{step_type}] {text}", file=sys.stderr)


# ─── Request builder ──────────────────────────────────────────────────────────


def _build_request(
    query: str,
    *,
    user_id: str,
    conversation_id: str,
    model: str | None,
    mode: str,
    route: str | None,
) -> AgentChatRequest:
    """Construct a minimal ``AgentChatRequestV3``."""
    route_metadata: dict[str, Any] = {"channel": "cli"}
    return AgentChatRequest(
        conversation_id=conversation_id,
        request=ChatRequest(query=query, model=model),
        context=ChatContext(route=route, route_metadata=route_metadata),
        mode=mode,
    )


# ─── Single-shot and REPL ─────────────────────────────────────────────────────


def _apply_config_overrides(args: argparse.Namespace) -> None:
    """Apply parsed CLI args over env-backed defaults."""
    cli_config.CLI_USER_ID = getattr(args, "user_id", None) or cli_config.CLI_USER_ID
    cli_config.CLI_BEARER_TOKEN = getattr(args, "api_key", None) or cli_config.CLI_BEARER_TOKEN
    cli_config.CLI_MEMORY_ROOT = getattr(args, "memory_root", None) or cli_config.CLI_MEMORY_ROOT
    cli_config.CLI_MODEL = getattr(args, "model", None) or cli_config.CLI_MODEL
    agent_config.MEMORY_ROOT = cli_config.CLI_MEMORY_ROOT


async def _run_query(
    query: str,
    *,
    user_id: str,
    bearer_token: str | None,
    memory_root: str,
    model: str | None,
    mode: str,
    route: str | None,
    verbose: bool,
    conversation_id: str = "cli-session",
) -> str:
    """Run one query through AgentRunner and return the response text."""
    runner = AgentRunner()
    sink = CliProgressSink(verbose=verbose)
    request = _build_request(
        query,
        user_id=user_id,
        conversation_id=conversation_id,
        model=model,
        mode=mode,
        route=route,
    )
    response = await runner.question(
        request,
        user_id=user_id,
        bearer_token=bearer_token,
        progress=sink,
    )
    return response.response.text or ""


def _run_once(args: argparse.Namespace) -> int:
    """Single-shot mode: run one query, print to stdout, return exit code."""
    query: str = args.once
    if not query:
        print("error: --once requires a non-empty query", file=sys.stderr)
        return 1

    mode = args.mode or "auto"
    route = args.route or None
    verbose = bool(args.verbose)
    if verbose:
        print(f"  user: {cli_config.CLI_USER_ID}  mode: {mode}", file=sys.stderr)

    text = asyncio.run(
        _run_query(
            query,
            user_id=cli_config.CLI_USER_ID,
            bearer_token=cli_config.CLI_BEARER_TOKEN or None,
            memory_root=cli_config.CLI_MEMORY_ROOT,
            model=cli_config.CLI_MODEL or None,
            mode=mode,
            route=route,
            verbose=verbose,
        )
    )
    print(text)
    return 0


def _run_repl(args: argparse.Namespace) -> int:
    """Interactive REPL: read queries from stdin, print responses to stdout."""
    mode = args.mode or "auto"
    route = args.route or None
    verbose = bool(args.verbose)
    print(
        f"ai-chat — user: {cli_config.CLI_USER_ID}  mode: {mode}" + (f"  model: {cli_config.CLI_MODEL}" if cli_config.CLI_MODEL else ""),
        file=sys.stderr,
    )
    print(
        'Type your query and press Enter. Type "exit" or Ctrl-D to quit.\n',
        file=sys.stderr,
    )

    conversation_id = f"cli-{os.getpid()}"
    turn = 0

    while True:
        try:
            query = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye.", file=sys.stderr)
            return 0

        if not query:
            continue
        if query.lower() in {"exit", "quit", "bye"}:
            print("bye.", file=sys.stderr)
            return 0

        turn += 1
        try:
            text = asyncio.run(
                _run_query(
                    query,
                    user_id=cli_config.CLI_USER_ID,
                    bearer_token=cli_config.CLI_BEARER_TOKEN or None,
                    memory_root=cli_config.CLI_MEMORY_ROOT,
                    model=cli_config.CLI_MODEL or None,
                    mode=mode,
                    route=route,
                    verbose=verbose,
                    conversation_id=conversation_id,
                )
            )
        except Exception as exc:  # noqa: BLE001
            print(f"error: {exc}", file=sys.stderr)
            continue

        print(f"\nai> {text}\n")

    return 0


# ─── Argument parser ──────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ai chat",
        description="Run the AI agent without FastAPI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ai chat --once 'What is AAPL PE?'\n"
            "  ai chat --model openai/gpt-4o --verbose\n"
            "  python -m ai.cli.main chat --once 'What is AAPL PE?'\n"
            "  ai-chat --once 'Summarise my watchlist' --user-id alice\n"
        ),
    )
    p.add_argument("--once", "-m", metavar="QUERY", help="Run a single query then exit.")
    p.add_argument("--user-id", dest="user_id", metavar="UID", help="User id (env: CLI_USER_ID).")
    p.add_argument(
        "--api-key",
        dest="api_key",
        metavar="KEY",
        help="Bearer token / API key (env: CLI_BEARER_TOKEN).",
    )
    p.add_argument("--model", metavar="MODEL", help="Model override, e.g. openai/gpt-4o.")
    p.add_argument("--mode", choices=["auto", "plan", "explain", "criticise"], default="auto")
    p.add_argument("--route", metavar="ROUTE", help="Automation route name.")
    p.add_argument(
        "--memory-root",
        dest="memory_root",
        metavar="DIR",
        help="Memory root dir (env: CLI_MEMORY_ROOT).",
    )
    p.add_argument("--verbose", "-v", action="store_true", help="Print CoT steps to stderr.")
    return p


# ─── Entry point ──────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> None:
    """Entry point for `ai-chat`, `ai chat`, and `python -m ai.cli chat`."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Override config with CLI args
    _apply_config_overrides(args)

    if args.once is not None:
        code = _run_once(args)
    else:
        code = _run_repl(args)

    raise SystemExit(code)
