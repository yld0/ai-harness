"""Automation run idempotency: duplicate ``automationRunId`` replay cache."""

from __future__ import annotations

import aiocache
import pytest
from fastapi.testclient import TestClient

import ai.api.automation_routes as ar_mod
from ai.main import app


def test_automation_run_replays_same_automation_run_id(
    auth_env: None,
    auth_headers,
    automation_payload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ar_mod, "replay_cache", aiocache.SimpleMemoryCache())

    with TestClient(app) as client:
        first = client.post(
            "/v3/agent/run",
            headers=auth_headers(),
            json=automation_payload("same-run"),
        )
        second = client.post(
            "/v3/agent/run",
            headers=auth_headers(),
            json={
                **automation_payload("same-run"),
                "input": {"watchlistID": "changed-but-replayed"},
            },
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()


def test_automation_run_idempotency_scoped_by_user(
    auth_env: None,
    auth_headers,
    automation_payload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ar_mod, "replay_cache", aiocache.SimpleMemoryCache())

    with TestClient(app) as client:
        first = client.post(
            "/v3/agent/run",
            headers=auth_headers("user-1"),
            json=automation_payload("same-run"),
        )
        second = client.post(
            "/v3/agent/run",
            headers=auth_headers("user-2"),
            json=automation_payload("same-run"),
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["metadata"]["user_id"] == "user-1"
    assert second.json()["metadata"]["user_id"] == "user-2"
