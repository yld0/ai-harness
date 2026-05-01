"""Top-level CLI (`ai` console script, ``python -m ai.cli``).

Dispatches to subcommands:
  chat    — interactive REPL or --once single-shot

Usage:
  ai chat [options]
  python -m ai.cli chat [options]
  python -m ai.cli chat --once "What is AAPL PE?"
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    top = argparse.ArgumentParser(
        prog="ai",
        description="AI harness agent — standalone CLI.",
        epilog="Run `ai <command> --help` or `python -m ai.cli <command> --help` for subcommand help.",
    )
    subs = top.add_subparsers(dest="command", metavar="COMMAND")
    subs.add_parser("chat", help="Start an agent chat session.", add_help=False)

    # Parse only the first positional so we can delegate the rest to the
    # subcommand's own parser (which handles --help correctly).
    first, remainder = top.parse_known_args()

    if first.command == "chat":
        from ai.cli.chat import main as chat_main

        chat_main(remainder)
    else:
        top.print_help()
        raise SystemExit(0)


if __name__ == "__main__":
    main()
