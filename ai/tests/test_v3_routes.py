import aiocache
import httpx
import pytest
from fastapi.testclient import TestClient

from ai.agent.runner import AgentRunner
from ai.main import app


def test_question_route_returns_agent_response(
    monkeypatch: pytest.MonkeyPatch,
    auth_env: None,
    auth_headers,
    chat_payload: dict,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v3/agent/question",
            headers=auth_headers(),
            json=chat_payload,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["conversationID"] == "conversation-1"
    assert body["response"]["text"].startswith("[stub]")
    assert body["metadata"]["user_id"] == "user-1"


def test_healthz_default_returns_skipped_deps() -> None:
    with TestClient(app) as client:
        health = client.get("/healthz")

    assert health.status_code == 200
    body = health.json()
    assert body["ok"] is True
    assert body["deps"] == {
        "graphql": "skipped",
        "gemini": "skipped",
        "openrouter": "skipped",
        "fmp": "skipped",
    }


def test_healthz_no_v2_registered() -> None:
    with TestClient(app) as client:
        missing_v2 = client.post("/v2/agent/question", json={})

    assert missing_v2.status_code == 404


def test_healthz_probe_deps_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    import ai.config as cfg_module

    monkeypatch.setattr(cfg_module.health_config, "HEALTHZ_PROBE_DEPS", True)
    monkeypatch.setattr(cfg_module.health_config, "GRAPHQL_HEALTH_URL", "http://graphql.test/healthz")
    monkeypatch.setattr(cfg_module.health_config, "OPENROUTER_HEALTH_URL", "https://openrouter.test/healthz")
    monkeypatch.setattr(cfg_module.health_config, "FMP_HEALTH_URL", "https://fmp.test")
    monkeypatch.setattr(cfg_module.health_config, "GEMINI_HEALTH_URL", "")

    async def _fake_head(self: object, url: str, **kwargs: object) -> httpx.Response:  # type: ignore[override]
        return httpx.Response(200)

    monkeypatch.setattr(httpx.AsyncClient, "head", _fake_head)

    with TestClient(app) as client:
        health = client.get("/healthz")

    assert health.status_code == 200
    body = health.json()
    assert body["ok"] is True
    assert body["deps"]["graphql"] == "200"
    assert body["deps"]["openrouter"] == "200"
    assert body["deps"]["fmp"] == "200"
    assert body["deps"]["gemini"] == "skipped"


def test_request_id_middleware_generates_and_echoes(
    auth_env: None,
    auth_headers,
    chat_payload: dict,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v3/agent/question",
            headers=auth_headers(),
            json=chat_payload,
        )
    assert response.status_code == 200
    rid = response.headers.get("X-Request-ID")
    assert rid is not None and len(rid) >= 8


def test_request_id_middleware_preserves_client_header(
    auth_env: None,
    auth_headers,
    chat_payload: dict,
) -> None:
    hdrs = auth_headers()
    hdrs["X-Request-ID"] = "client-correlation-abc"
    with TestClient(app) as client:
        response = client.post(
            "/v3/agent/question",
            headers=hdrs,
            json=chat_payload,
        )
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "client-correlation-abc"


def test_run_agent_returns_agent_response(
    auth_env: None,
    auth_headers,
    automation_payload,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v3/agent/run",
            headers=auth_headers(),
            json=automation_payload("run-success-1"),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["response"]["text"].startswith("[stub]")
    assert body["metadata"]["user_id"] == "user-1"


def test_run_agent_replays_cached_result_for_same_run_id(
    auth_env: None,
    auth_headers,
    automation_payload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ai.api.automation_routes as ar_mod

    run_calls: list[str] = []
    original_run = AgentRunner.run

    async def counting_run(self, body, *, user_id, bearer_token=None, **kwargs):  # type: ignore[override]
        """Counting wrapper around AgentRunner.run for test assertion."""
        run_calls.append(body.automation_run_id)
        return await original_run(self, body, user_id=user_id, bearer_token=bearer_token, **kwargs)

    monkeypatch.setattr(AgentRunner, "run", counting_run)
    monkeypatch.setattr(ar_mod, "replay_cache", aiocache.SimpleMemoryCache())

    payload = automation_payload("run-replay-1")
    with TestClient(app) as client:
        r1 = client.post("/v3/agent/run", headers=auth_headers(), json=payload)
        r2 = client.post("/v3/agent/run", headers=auth_headers(), json=payload)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json() == r2.json()
    assert len(run_calls) == 1


def test_run_agent_forwards_bearer_token_to_runner(
    auth_env: None,
    auth_token,
    automation_payload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ai.api.automation_routes as ar_mod

    captured: list[str | None] = []
    original_run = AgentRunner.run

    async def capturing_run(self, body, *, user_id, bearer_token=None, **kwargs):  # type: ignore[override]
        """Capturing wrapper around AgentRunner.run for test assertion."""
        captured.append(bearer_token)
        return await original_run(self, body, user_id=user_id, bearer_token=bearer_token, **kwargs)

    monkeypatch.setattr(AgentRunner, "run", capturing_run)
    monkeypatch.setattr(ar_mod, "replay_cache", aiocache.SimpleMemoryCache())

    token = auth_token("user-1")
    with TestClient(app) as client:
        response = client.post(
            "/v3/agent/run",
            headers={"Authorization": f"Bearer {token}"},
            json=automation_payload("run-bearer-1"),
        )

    assert response.status_code == 200
    assert len(captured) == 1
    assert captured[0] == token
