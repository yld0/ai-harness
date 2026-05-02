"""Telemetry initializes without crashing; backends honor env toggles (mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from ai.main import app
from ai.telemetry import setup_telemetry
from ai.telemetry.langfuse import init_langfuse, reset_langfuse_client
from ai.telemetry.posthog import capture_event, init_posthog, reset_posthog_client
from ai.telemetry.sentry import capture_exception, init_sentry


@pytest.fixture(autouse=True)
def _reset_telemetry_singletons() -> None:
    reset_langfuse_client()
    reset_posthog_client()
    yield
    reset_langfuse_client()
    reset_posthog_client()


def test_setup_telemetry_no_env_no_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.delenv("POSTHOG_API_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    setup_telemetry()


def test_app_lifespan_runs_setup_telemetry_without_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.delenv("POSTHOG_API_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200


def test_sentry_init_when_dsn_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTRY_DSN", "https://examplePublicKey@o0.ingest.sentry.io/0")
    mock_sdk = MagicMock()
    init_sentry(loader=lambda: mock_sdk)
    mock_sdk.init.assert_called_once()
    kwargs = mock_sdk.init.call_args.kwargs
    assert "dsn" in kwargs


def test_sentry_capture_exception_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_cap = MagicMock()
    import sentry_sdk

    monkeypatch.setattr(sentry_sdk, "capture_exception", mock_cap)
    capture_exception(ValueError("x"))
    mock_cap.assert_called_once()


def test_posthog_configured_when_key_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "phc_test")
    kwargs: dict = {}

    def factory(**kw: object) -> MagicMock:
        kwargs.update(kw)
        return MagicMock()

    init_posthog(factory=factory)
    assert kwargs["project_api_key"] == "phc_test"
    assert "app.posthog.com" in str(kwargs.get("host", ""))


def test_posthog_capture_event_routes_to_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "phc_test")
    mock_client = MagicMock()
    init_posthog(factory=lambda **_: mock_client)
    capture_event("user-sub-1", "test_event", {"a": 1})
    mock_client.capture.assert_called_once()
    call_kw = mock_client.capture.call_args.kwargs
    assert call_kw["distinct_id"] == "user-sub-1"
    assert call_kw["event"] == "test_event"


def test_langfuse_client_constructed_when_keys_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    mock_cls = MagicMock(return_value=MagicMock(name="langfuse_instance"))
    init_langfuse(factory=lambda: mock_cls)
    mock_cls.assert_called_once()
    kwargs = mock_cls.call_args.kwargs
    assert kwargs["public_key"] == "pk-test"
    assert kwargs["secret_key"] == "sk-test"


@pytest.mark.asyncio
async def test_langfuse_trace_context_managers_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agent root observation + provider generation span for echo provider."""
    monkeypatch.delenv("GENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("DEV_ECHO_MODE", "true")

    mock_obs_cm = MagicMock()
    mock_obs_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_obs_cm.__exit__ = MagicMock(return_value=None)

    mock_lf = MagicMock()
    mock_lf.create_trace_id.return_value = "traceidtraceidtraceidtraceid12"
    mock_lf.start_as_current_observation.return_value = mock_obs_cm

    mock_prop_cm = MagicMock()
    mock_prop_cm.__enter__ = MagicMock(return_value=None)
    mock_prop_cm.__exit__ = MagicMock(return_value=None)

    monkeypatch.setattr("ai.agent.runner.get_langfuse_client", lambda: mock_lf)
    monkeypatch.setattr("langfuse.propagate_attributes", lambda **_: mock_prop_cm)

    from ai.agent.runner import AgentRunner
    from ai.schemas.agent import AgentChatRequest

    req = AgentChatRequest.model_validate(
        {
            "conversationID": "c1",
            "request": {"query": "hello"},
            "context": {"route": "chats", "routeMetadata": {}},
            "mode": "auto",
        }
    )
    runner = AgentRunner()
    await runner.run_chat_turn(req, user_id="u1")

    assert mock_lf.start_as_current_observation.call_count >= 2
