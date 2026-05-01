"""Standalone CLI chat loop — no FastAPI required.

Usage examples:

    # Single-shot (exits 0 on success):
    ai chat --once "What is AAPL PE?"

    # Interactive REPL:
    ai chat

    # With options:
    ai chat --model openai/gpt-4o --mode plan --user-id alice

    # Equivalent: python -m ai.cli chat ...

Environment variables (all optional):
    YLD_JWT          — Bearer token forwarded to GraphQL tools.
    CLI_USER_ID      — Default user id (default: cli-user).
    MEMORY_ROOT      — Root directory for PARA memory files.
    DEV_ECHO_MODE — Set to True for deterministic offline testing.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any, Optional

from ai.agent.progress import ProgressSink

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
    model: Optional[str],
    mode: str,
    route: Optional[str],
):
    """Construct a minimal ``AgentChatRequestV3`` — imported lazily to keep
    the cold-start path free of heavy deps."""
    from ai.schemas.agent import AgentChatRequest, ChatContext, ChatRequest

    route_metadata: dict[str, Any] = {"channel": "cli"}
    return AgentChatRequest(
        conversation_id=conversation_id,
        request=ChatRequest(query=query, model=model),
        context=ChatContext(route=route, route_metadata=route_metadata),
        mode=mode,
    )


# ─── Single-shot and REPL ─────────────────────────────────────────────────────


async def _run_query(
    query: str,
    *,
    user_id: str,
    bearer_token: Optional[str],
    model: Optional[str],
    mode: str,
    route: Optional[str],
    verbose: bool,
    conversation_id: str = "cli-session",
) -> str:
    """Run one query through AgentRunner and return the response text."""
    from ai.agent.runner import AgentRunner

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


def _run_once(args: argparse.Namespace, cfg) -> int:
    """Single-shot mode: run one query, print to stdout, return exit code."""
    query: str = args.once
    if not query:
        print("error: --once requires a non-empty query", file=sys.stderr)
        return 1

    if cfg.verbose:
        print(f"  user: {cfg.user_id}  mode: {cfg.mode}", file=sys.stderr)

    text = asyncio.run(
        _run_query(
            query,
            user_id=cfg.user_id,
            bearer_token=cfg.bearer_token,
            model=cfg.model,
            mode=cfg.mode,
            route=cfg.route,
            verbose=cfg.verbose,
        )
    )
    print(text)
    return 0


def _run_repl(args: argparse.Namespace, cfg) -> int:
    """Interactive REPL: read queries from stdin, print responses to stdout."""
    print(
        f"ai-chat — user: {cfg.user_id}  mode: {cfg.mode}" + (f"  model: {cfg.model}" if cfg.model else ""),
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
                    user_id=cfg.user_id,
                    bearer_token=cfg.bearer_token,
                    model=cfg.model,
                    mode=cfg.mode,
                    route=cfg.route,
                    verbose=cfg.verbose,
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
            "  python -m ai.cli chat --once 'What is AAPL PE?'\n"
            "  ai-chat --once 'Summarise my watchlist' --user-id alice\n"
        ),
    )
    p.add_argument("--once", "-m", metavar="QUERY", help="Run a single query then exit.")
    p.add_argument("--user-id", dest="user_id", metavar="UID", help="User id (env: CLI_USER_ID).")
    p.add_argument(
        "--api-key",
        dest="api_key",
        metavar="KEY",
        help="Bearer token / API key (env: YLD_JWT).",
    )
    p.add_argument("--model", metavar="MODEL", help="Model override, e.g. openai/gpt-4o.")
    p.add_argument("--mode", choices=["auto", "plan", "explain", "criticise"], default="auto")
    p.add_argument("--route", metavar="ROUTE", help="Automation route name.")
    p.add_argument(
        "--memory-root",
        dest="memory_root",
        metavar="DIR",
        help="Memory root dir (env: MEMORY_ROOT).",
    )
    p.add_argument("--env-file", dest="env_file", metavar="FILE", help="Path to .env file.")
    p.add_argument("--verbose", "-v", action="store_true", help="Print CoT steps to stderr.")
    return p


# ─── Entry point ──────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> None:
    """Entry point for `ai-chat`, `ai chat`, and `python -m ai.cli chat`."""
    from ai.cli.config import resolve_config
    from pathlib import Path

    parser = _build_parser()
    args = parser.parse_args(argv)
    env_file = Path(args.env_file) if args.env_file else None
    cfg = resolve_config(args, env_file=env_file)

    if args.once is not None:
        code = _run_once(args, cfg)
    else:
        code = _run_repl(args, cfg)

    raise SystemExit(code)
