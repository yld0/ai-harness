"""CLI configuration: load .env then merge with argparse namespace."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _load_dotenv(env_file: Path | None = None) -> None:
    """Best-effort .env loader.  Requires python-dotenv; skips silently if absent."""
    try:
        from dotenv import load_dotenv  # type: ignore[import-untyped]
    except ImportError:
        return
    path = env_file or _find_dotenv()
    if path is not None and path.is_file():
        load_dotenv(path, override=False)


def _find_dotenv() -> Optional[Path]:
    """Walk upward from cwd looking for .env (stop at repo root)."""
    cur = Path.cwd()
    for _ in range(6):
        candidate = cur / ".env"
        if candidate.is_file():
            return candidate
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    return None


@dataclass
class CliConfig:
    """Resolved configuration for a single CLI session."""

    user_id: str
    bearer_token: Optional[str]
    memory_root: str
    model: Optional[str]
    mode: str  # auto | plan | explain | criticise
    route: Optional[str]
    verbose: bool  # print CoT steps to stderr
    env_file: Optional[Path]


def resolve_config(args: object, env_file: Path | None = None) -> CliConfig:
    """Merge env (after .env load) with parsed argparse *args*.

    *args* is the namespace from argparse.  Precedence: CLI flag > env var > default.
    """
    _load_dotenv(env_file or getattr(args, "env_file", None))

    user_id: str = getattr(args, "user_id", None) or os.getenv("CLI_USER_ID") or os.getenv("YLD_USER_ID") or "cli-user"
    bearer_token: Optional[str] = getattr(args, "api_key", None) or os.getenv("YLD_JWT") or os.getenv("API_KEY") or None
    memory_root: str = getattr(args, "memory_root", None) or os.getenv("MEMORY_ROOT") or "./memory"
    model: Optional[str] = getattr(args, "model", None) or os.getenv("CLI_MODEL") or None
    mode: str = getattr(args, "mode", None) or "auto"
    route: Optional[str] = getattr(args, "route", None) or None
    verbose: bool = bool(getattr(args, "verbose", False))

    return CliConfig(
        user_id=user_id,
        bearer_token=bearer_token,
        memory_root=memory_root,
        model=model,
        mode=mode,
        route=route,
        verbose=verbose,
        env_file=env_file,
    )
