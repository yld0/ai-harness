"""Shared pytest fixtures for the AI harness."""

from __future__ import annotations

import jwt
import pytest

import ai.agent.runner as _ai_runner
from ai.agent.loop import ProviderMessage, ProviderTurn


class StubProvider:
    """Deterministic test double for the LLM provider.

    Echoes the last user message so tests can assert on round-trip behaviour
    without hitting a real API.
    """

    async def complete(self, messages: list[ProviderMessage], *, tools_enabled: bool, effort: str) -> ProviderTurn:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return ProviderTurn(content=f"[stub] {last_user}", finish_reason="stop")


@pytest.fixture(autouse=True)
def _stub_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch AgentRunner._default_provider so tests never need real API keys."""
    monkeypatch.setattr(
        _ai_runner.AgentRunner,
        "_default_provider",
        staticmethod(lambda: StubProvider()),
    )


@pytest.fixture
def jwt_secret() -> str:
    return "test-secret"


@pytest.fixture
def auth_token(jwt_secret: str):
    def _token(user_id: str = "user-1") -> str:
        return jwt.encode({"sub": user_id}, jwt_secret, algorithm="HS256")

    return _token


@pytest.fixture
def auth_headers(auth_token):
    def _headers(user_id: str = "user-1") -> dict[str, str]:
        return {"Authorization": f"Bearer {auth_token(user_id)}"}

    return _headers


@pytest.fixture
def auth_env(monkeypatch, jwt_secret: str) -> None:
    monkeypatch.setenv("AUTH_SECRETPHRASE", jwt_secret)


@pytest.fixture
def chat_payload() -> dict:
    return {
        "conversationID": "conversation-1",
        "request": {"query": "Compare Apple and Microsoft"},
        "context": {"route": "chats", "stocks": ["AAPL", "MSFT"]},
        "mode": "auto",
    }


@pytest.fixture
def automation_payload(chat_payload: dict):
    def _make(run_id: str = "run-1") -> dict:
        return {
            **chat_payload,
            "automationId": "automation-1",
            "automationRunId": run_id,
            "route": "actions-catchup",
            "target": "watchlist",
            "input": {"watchlistID": "watchlist-1"},
        }

    return _make


@pytest.fixture
def tmp_memory_root(monkeypatch: pytest.MonkeyPatch, tmp_path) -> str:
    root = str(tmp_path / "memory")
    monkeypatch.setenv("MEMORY_ROOT", root)
    return root


@pytest.fixture
def project_root() -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parents[1])
