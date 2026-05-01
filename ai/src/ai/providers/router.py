"""Model/provider router with effort routing and transient fallback."""

from dataclasses import dataclass, replace
from time import monotonic, sleep
from typing import Any

from ai.agent.loop import ProviderMessage, ProviderTurn
from ai.providers.base import (
    ProviderClient,
    ProviderEffort,
    ProviderRequest,
    ProviderResponse,
)
from ai.providers.errors import ProviderError, classify_provider_error
from ai.providers.gemini import GeminiClient
from ai.providers.models import capabilities_for, model_for_effort
from ai.providers.openrouter import OpenRouterClient
from ai.usage.capture import capture as _capture_usage

COOLDOWN_SECONDS = [60, 300, 1500, 3600]


@dataclass(frozen=True)
class RouterOptions:
    model_override: str | None = None
    tools: list[dict[str, Any]] | None = None
    response_format: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    request_thinking: bool = False


class ProviderRouter:
    def __init__(
        self,
        *,
        clients: dict[str, ProviderClient] | None = None,
        fallback_models: list[str] | None = None,
        options: RouterOptions | None = None,
        cooldowns: dict[tuple[str, str], tuple[float, int]] | None = None,
        max_retries_per_model: int = 1,
    ) -> None:
        self.clients = clients or {
            "gemini": GeminiClient(),
            "openrouter": OpenRouterClient(),
        }
        self.fallback_models = fallback_models or []
        self.options = options or RouterOptions()
        self.cooldowns = cooldowns if cooldowns is not None else {}
        self.max_retries_per_model = max_retries_per_model

    def with_options(
        self,
        *,
        model_override: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        request_thinking: bool = False,
    ) -> "ProviderRouter":
        return ProviderRouter(
            clients=self.clients,
            fallback_models=self.fallback_models,
            options=replace(
                self.options,
                model_override=model_override,
                tools=tools,
                response_format=response_format,
                metadata=metadata,
                request_thinking=request_thinking,
            ),
            cooldowns=self.cooldowns,
            max_retries_per_model=self.max_retries_per_model,
        )

    async def complete(self, messages: list[ProviderMessage], *, tools_enabled: bool, effort: str) -> ProviderTurn:
        response = await self.generate(
            ProviderRequest(
                messages=messages,
                model=self.options.model_override or model_for_effort(effort),
                effort=effort if effort in {"low", "medium", "high"} else "low",  # type: ignore[arg-type]
                tools=(self.options.tools or []) if tools_enabled else [],
                response_format=self.options.response_format,
                metadata=self.options.metadata or {},
                request_thinking=self.options.request_thinking,
            )
        )
        metadata = {
            "provider": response.provider,
            "model": response.model,
            "usage": response.usage,
            "raw_ref": response.raw_ref,
        }
        if response.thinking_text:
            metadata["thinking_text"] = response.thinking_text
        return ProviderTurn(
            content=response.text,
            tool_calls=response.tool_calls,
            finish_reason=response.finish_reason,
            metadata=metadata,
        )

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        last_error: ProviderError | None = None
        for model in self._candidate_models(request.model):
            provider_name = capabilities_for(model).provider
            if self._is_on_cooldown(model, provider_name):
                continue
            client = self.clients[provider_name]
            candidate = replace(request, model=model)
            for attempt in range(self.max_retries_per_model + 1):
                try:
                    response = await client.generate(candidate)
                    # TODO: Uncomment this when we have a way to capture usage
                    # await _capture_usage(response)
                    return response
                except Exception as exc:
                    last_error = classify_provider_error(exc, provider=provider_name, model=model)
                    if not last_error.retryable:
                        raise last_error
                    if attempt >= self.max_retries_per_model:
                        self._cooldown(model, provider_name, last_error)
                        break
                    sleep(0)
        if last_error is not None:
            raise last_error
        raise ProviderError("No provider models available", kind="unknown", retryable=False)

    def select_model(self, *, effort: ProviderEffort, model_override: str | None = None) -> str:
        return model_override or model_for_effort(effort)

    def select_provider(self, model: str) -> ProviderClient:
        return self.clients[capabilities_for(model).provider]

    def _candidate_models(self, primary: str) -> list[str]:
        models = [primary, *self.fallback_models]
        deduped: list[str] = []
        for model in models:
            if model not in deduped:
                deduped.append(model)
        return deduped

    def _is_on_cooldown(self, model: str, provider: str) -> bool:
        item = self.cooldowns.get((provider, model))
        if item is None:
            return False
        until, _level = item
        if monotonic() >= until:
            self.cooldowns.pop((provider, model), None)
            return False
        return True

    def _cooldown(self, model: str, provider: str, error: ProviderError) -> None:
        if error.kind == "auth":
            return
        _until, level = self.cooldowns.get((provider, model), (0.0, -1))
        next_level = min(level + 1, len(COOLDOWN_SECONDS) - 1)
        self.cooldowns[(provider, model)] = (
            monotonic() + COOLDOWN_SECONDS[next_level],
            next_level,
        )
