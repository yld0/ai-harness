"""Single-turn LLM completions without a persisted conversation (for hooks / batch tasks)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from ai.agent.loop import ProviderMessage
from ai.config import agent_config
from ai.providers.base import ProviderRequest
from ai.providers.models import model_for_effort
from ai.providers.router import ProviderRouter

LLMCaller = Callable[[str], Awaitable[str]]


def one_shot_caller(
    *,
    model_override: str | None = None,
    system_message: str | None = None,
) -> LLMCaller:
    """
    Build an async callable that sends one user prompt and returns assistant text.

    Uses :class:`~ai.providers.router.ProviderRouter` with ``agent_config.AI_FALLBACK_MODELS``.
    When *model_override* is empty, the default ``low`` effort router model is used.
    """

    resolved_model = (model_override or "").strip() or model_for_effort("low")

    router = ProviderRouter(fallback_models=agent_config.AI_FALLBACK_MODELS)

    async def call_llm(prompt: str) -> str:
        messages: list[ProviderMessage] = []
        if system_message and system_message.strip():
            messages.append(ProviderMessage(role="system", content=system_message.strip()))
        messages.append(ProviderMessage(role="user", content=prompt))
        response = await router.generate(
            ProviderRequest(
                messages=messages,
                model=resolved_model,
                effort="low",
            )
        )
        return response.text or ""

    return call_llm
