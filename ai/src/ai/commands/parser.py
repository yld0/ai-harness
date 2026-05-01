"""Parse leading /command [args...] from a user message.

Supports:
- Simple tokens: /skill list
- Quoted arguments: /skill view "my skill name"
- Multi-word first line; remainder text (after newline) is preserved.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass


@dataclass
class ParsedCommand:
    name: str
    args: list[str]
    raw: str  # original first-line text
    remainder: str  # any text after the first line


def parse_slash_command(text: str) -> ParsedCommand | None:
    """Return a ParsedCommand if *text* starts with a slash command, else None."""
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None

    first_line, _, rest = stripped.partition("\n")
    first_line = first_line.strip()
    if not first_line:
        return None

    try:
        tokens = shlex.split(first_line)
    except ValueError:
        # Unmatched quotes — fall back to whitespace split
        tokens = first_line.split()

    if not tokens:
        return None

    name_raw = tokens[0].lstrip("/")
    if not name_raw:
        return None

    return ParsedCommand(
        name=name_raw.lower(),
        args=tokens[1:],
        raw=first_line,
        remainder=rest.strip(),
    )
