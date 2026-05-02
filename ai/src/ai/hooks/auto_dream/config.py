"""Auto-dream scheduling helpers (reads :class:`ai.config.HookConfig`)."""

from __future__ import annotations

from ai.config import hook_config


def is_auto_dream_enabled() -> bool:
    """Return whether periodic memory consolidation is permitted at the config layer."""
    return hook_config.AI_AUTO_DREAM_ENABLED
