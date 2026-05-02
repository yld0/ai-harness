"""Stable import path for hook contracts (:class:`~ai.hooks.types`) and helpers."""

from __future__ import annotations

from typing import Any, cast

from ai.config import HookConfig, hook_config
from ai.hooks.types import Hook, HookContext, HookResult
from ai.schemas.agent import AgentChatRequest
from shared.envutil.config import load


def load_hook_config() -> HookConfig:
    """Load :class:`~ai.config.HookConfig` from the current environment (fresh read)."""

    return load(HookConfig)


def build_hook_context(
    *,
    user_id: str,
    conversation_id: str,
    user_message: str,
    response_text: str,
    request: AgentChatRequest | Any,
    messages: list[Any],
    turn_index: int,
    config: HookConfig | None = None,
) -> HookContext:
    """Construct a :class:`~ai.hooks.types.HookContext` for HTTP or websocket turn completion."""

    return HookContext(
        user_id=user_id,
        conversation_id=conversation_id,
        user_message=user_message,
        response_text=response_text,
        request=cast(AgentChatRequest, request),
        messages=messages,
        config=config or hook_config,
        turn_index=turn_index,
    )


__all__ = [
    "Hook",
    "HookConfig",
    "HookContext",
    "HookResult",
    "build_hook_context",
    "hook_config",
    "load_hook_config",
]
