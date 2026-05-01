"""Hook contracts: post-turn processing after the client has the final response."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ai.schemas.agent import AgentChatRequest

logger = logging.getLogger(__name__)


@dataclass
class HookConfig:
    """Per-process hook flags and thresholds (env-backed in `load_hook_config`)."""

    hooks_enabled: list[str] = field(default_factory=list)
    compact_soft_chars: int = 12_000
    collapse_hard_chars: int = 48_000
    keep_recent_pairs: int = 3
    auto_dream_every_n_turns: int = 5
    post_hook_timeout_s: float = 30.0
    skill_review_threshold: int = 10


@dataclass
class HookContext:
    user_id: str
    conversation_id: str
    user_message: str
    response_text: str
    request: "AgentChatRequest | Any"
    messages: list[Any]
    config: HookConfig
    turn_index: int = 0


@dataclass
class HookResult:
    name: str
    ok: bool
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Hook(Protocol):
    name: str

    def run(self, ctx: HookContext) -> HookResult: ...


def build_hook_context(
    *,
    user_id: str,
    conversation_id: str,
    user_message: str,
    response_text: str,
    request: Any,
    messages: list[Any],
    turn_index: int,
    config: HookConfig | None = None,
) -> HookContext:
    return HookContext(
        user_id=user_id,
        conversation_id=conversation_id,
        user_message=user_message,
        response_text=response_text,
        request=request,
        messages=messages,
        config=config or load_hook_config(),
        turn_index=turn_index,
    )


def load_hook_config() -> HookConfig:
    import os

    raw = (os.environ.get("AI_HOOKS_ENABLED") or "").strip()
    enabled = [p.strip() for p in raw.split(",") if p.strip()] if raw else []
    return HookConfig(
        hooks_enabled=enabled,
        compact_soft_chars=int(os.environ.get("AI_COMPACT_SOFT_CHARS", "12000")),
        collapse_hard_chars=int(os.environ.get("AI_COLLAPSE_HARD_CHARS", "48000")),
        keep_recent_pairs=int(os.environ.get("AI_COLLAPSE_KEEP_PAIRS", "3")),
        auto_dream_every_n_turns=int(os.environ.get("AI_AUTO_DREAM_EVERY_N", "5")),
        post_hook_timeout_s=float(os.environ.get("AI_POST_HOOK_TIMEOUT_S", "30")),
        skill_review_threshold=int(os.environ.get("AI_SKILL_REVIEW_THRESHOLD", "10")),
    )
