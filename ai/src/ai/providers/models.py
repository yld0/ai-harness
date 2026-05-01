"""Small model catalog for routing decisions."""

import os
from dataclasses import dataclass
from typing import Literal

ProviderName = Literal["gemini", "openrouter"]
ProviderEffort = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class ModelCapabilities:
    model_id: str
    provider: ProviderName
    supports_tools: bool
    supports_streaming: bool
    supports_vision: bool
    max_context_tokens: int
    max_output_tokens: int
    reasoning: bool = False


DEFAULT_GEMINI_FLASH = os.getenv("AI_GEMINI_FLASH_MODEL", "gemini-2.5-flash")
DEFAULT_GEMINI_PRO = os.getenv("AI_GEMINI_PRO_MODEL", "gemini-2.5-pro")
DEFAULT_OPENROUTER_REASONING = os.getenv(
    "AI_OPENROUTER_REASONING_MODEL",
    "anthropic/claude-3.7-sonnet:thinking",
)


CATALOG: dict[str, ModelCapabilities] = {
    DEFAULT_GEMINI_FLASH: ModelCapabilities(
        model_id=DEFAULT_GEMINI_FLASH,
        provider="gemini",
        supports_tools=True,
        supports_streaming=True,
        supports_vision=True,
        max_context_tokens=1_000_000,
        max_output_tokens=65_536,
    ),
    DEFAULT_GEMINI_PRO: ModelCapabilities(
        model_id=DEFAULT_GEMINI_PRO,
        provider="gemini",
        supports_tools=True,
        supports_streaming=True,
        supports_vision=True,
        max_context_tokens=1_000_000,
        max_output_tokens=65_536,
        reasoning=True,
    ),
    DEFAULT_OPENROUTER_REASONING: ModelCapabilities(
        model_id=DEFAULT_OPENROUTER_REASONING,
        provider="openrouter",
        supports_tools=True,
        supports_streaming=True,
        supports_vision=True,
        max_context_tokens=200_000,
        max_output_tokens=32_000,
        reasoning=True,
    ),
}


def model_for_effort(effort: str) -> str:
    if effort == "high":
        return os.getenv("AI_HIGH_MODEL", DEFAULT_OPENROUTER_REASONING)
    if effort == "medium":
        return os.getenv("AI_MEDIUM_MODEL", DEFAULT_GEMINI_PRO)
    return os.getenv("AI_LOW_MODEL", DEFAULT_GEMINI_FLASH)


def capabilities_for(model_id: str) -> ModelCapabilities:
    if model_id in CATALOG:
        return CATALOG[model_id]
    if model_id.startswith("gemini-"):
        return ModelCapabilities(
            model_id=model_id,
            provider="gemini",
            supports_tools=True,
            supports_streaming=True,
            supports_vision=True,
            max_context_tokens=1_000_000,
            max_output_tokens=65_536,
        )
    return ModelCapabilities(
        model_id=model_id,
        provider="openrouter",
        supports_tools=True,
        supports_streaming=True,
        supports_vision=True,
        max_context_tokens=200_000,
        max_output_tokens=32_000,
        reasoning="thinking" in model_id or "reasoning" in model_id,
    )
