import asyncio

import pytest

from ai.agent.loop import ProviderMessage
from ai.providers.base import ProviderRequest, ProviderResponse
from ai.providers.errors import ProviderRateLimitError
from ai.providers.router import ProviderRouter


class FakeClient:
    def __init__(self, name: str, *, failures: list[Exception] | None = None) -> None:
        self.name = name
        self.failures = failures or []
        self.requests: list[ProviderRequest] = []

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        if self.failures:
            raise self.failures.pop(0)
        return ProviderResponse(
            text=f"{self.name}:{request.model}",
            usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            provider=self.name,
            finish_reason="stop",
            model=request.model,
        )


def test_effort_routes_to_expected_provider() -> None:
    async def run() -> None:
        gemini = FakeClient("gemini")
        openrouter = FakeClient("openrouter")
        router = ProviderRouter(clients={"gemini": gemini, "openrouter": openrouter})

        low = await router.complete(
            [ProviderMessage(role="user", content="low")],
            tools_enabled=True,
            effort="low",
        )
        high = await router.complete(
            [ProviderMessage(role="user", content="high")],
            tools_enabled=True,
            effort="high",
        )

        assert low.metadata["provider"] == "gemini"
        assert low.metadata["model"] == "gemini-2.5-flash"
        assert high.metadata["provider"] == "openrouter"
        assert "claude" in high.metadata["model"]

    asyncio.run(run())


def test_explicit_model_override_wins() -> None:
    async def run() -> None:
        openrouter = FakeClient("openrouter")
        router = ProviderRouter(clients={"gemini": FakeClient("gemini"), "openrouter": openrouter}).with_options(
            model_override="openai/gpt-4.1-mini"
        )

        turn = await router.complete(
            [ProviderMessage(role="user", content="override")],
            tools_enabled=True,
            effort="low",
        )

        assert turn.metadata["provider"] == "openrouter"
        assert turn.metadata["model"] == "openai/gpt-4.1-mini"
        assert openrouter.requests[0].model == "openai/gpt-4.1-mini"

    asyncio.run(run())


def test_fallback_on_injected_429_and_captures_usage() -> None:
    async def run() -> None:
        gemini = FakeClient(
            "gemini",
            failures=[ProviderRateLimitError("slow down", provider="gemini", model="gemini-2.5-flash")],
        )
        openrouter = FakeClient("openrouter")
        router = ProviderRouter(
            clients={"gemini": gemini, "openrouter": openrouter},
            fallback_models=["anthropic/claude-3.7-sonnet:thinking"],
            max_retries_per_model=0,
        )

        response = await router.generate(
            ProviderRequest(
                messages=[ProviderMessage(role="user", content="fallback")],
                model="gemini-2.5-flash",
            )
        )

        assert response.provider == "openrouter"
        assert response.model == "anthropic/claude-3.7-sonnet:thinking"
        assert ("gemini", "gemini-2.5-flash") in router.cooldowns

    asyncio.run(run())


def test_thinking_flag_and_tool_schema_reach_provider() -> None:
    async def run() -> None:
        openrouter = FakeClient("openrouter")
        router = ProviderRouter(clients={"gemini": FakeClient("gemini"), "openrouter": openrouter}).with_options(
            model_override="anthropic/claude-3.7-sonnet:thinking",
            request_thinking=True,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "lookup",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
        )

        await router.complete(
            [ProviderMessage(role="user", content="tools")],
            tools_enabled=True,
            effort="high",
        )

        assert openrouter.requests[0].request_thinking is True
        assert openrouter.requests[0].tools[0]["function"]["name"] == "lookup"

    asyncio.run(run())


def test_auth_errors_fail_fast_without_fallback() -> None:
    async def run() -> None:
        from ai.providers.errors import ProviderAuthError

        router = ProviderRouter(
            clients={
                "gemini": FakeClient("gemini", failures=[ProviderAuthError("bad key")]),
                "openrouter": FakeClient("openrouter"),
            },
            fallback_models=["anthropic/claude-3.7-sonnet:thinking"],
        )

        with pytest.raises(ProviderAuthError):
            await router.generate(
                ProviderRequest(
                    messages=[ProviderMessage(role="user", content="auth")],
                    model="gemini-2.5-flash",
                )
            )

    asyncio.run(run())
