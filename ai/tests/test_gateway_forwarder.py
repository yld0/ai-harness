"""Tests for the gateway HTTP forwarder (Phase 17).

All HTTP calls are intercepted with respx.  No neonize or discord.py needed.
"""

from __future__ import annotations

import pytest
import respx
import httpx

from ai.gateway.http_forwarder import (
    HarnessForwarder,
    RateLimiter,
    RateLimitError,
    build_request_body,
)

_HARNESS = "http://localhost:8005"
_URL = f"{_HARNESS}/v3/agent/question"


# ─── build_request_body ───────────────────────────────────────────────────────


def test_build_request_body_minimal():
    body = build_request_body("hello", user_id="u1", conversation_id="c1")
    assert body["request"]["query"] == "hello"
    assert body["conversationId"] == "c1"
    assert body["context"]["routeMetadata"]["channel"] == "whatsapp"
    assert body["mode"] == "auto"


def test_build_request_body_channel_override():
    body = build_request_body("hi", user_id="u1", conversation_id="c1", channel="discord")
    assert body["context"]["routeMetadata"]["channel"] == "discord"


def test_build_request_body_model_included():
    body = build_request_body("q", user_id="u1", conversation_id="c1", model="gpt-4o")
    assert body["request"]["model"] == "gpt-4o"


def test_build_request_body_no_model_key_when_not_set():
    body = build_request_body("q", user_id="u1", conversation_id="c1")
    assert "model" not in body["request"]


def test_build_request_body_mode_plan():
    body = build_request_body("q", user_id="u1", conversation_id="c1", mode="plan")
    assert body["mode"] == "plan"


# ─── HarnessForwarder — happy path ────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_forwarder_posts_to_v3_endpoint():
    mock = respx.post(_URL).mock(return_value=httpx.Response(200, json={"response": {"text": "pong"}}))
    fwd = HarnessForwarder(harness_url=_HARNESS, bearer_token="tok", rate_limiter=None)
    result = await fwd.forward("ping", user_id="u1", conversation_id="c1")
    assert result == "pong"
    assert mock.called


@pytest.mark.asyncio
@respx.mock
async def test_forwarder_sets_authorization_header():
    mock = respx.post(_URL).mock(return_value=httpx.Response(200, json={"response": {"text": "ok"}}))
    fwd = HarnessForwarder(harness_url=_HARNESS, bearer_token="my-jwt", rate_limiter=None)
    await fwd.forward("hi", user_id="u1", conversation_id="c1")
    assert mock.calls[0].request.headers["Authorization"] == "Bearer my-jwt"


@pytest.mark.asyncio
@respx.mock
async def test_forwarder_request_body_matches_v3_schema():
    captured = {}

    async def _handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"response": {"text": "reply"}})

    respx.post(_URL).mock(side_effect=_handler)
    fwd = HarnessForwarder(harness_url=_HARNESS, bearer_token="", rate_limiter=None)
    await fwd.forward(
        "What is AAPL PE?",
        user_id="alice",
        conversation_id="sess-1",
        channel="whatsapp",
    )

    body = captured["body"]
    assert body["request"]["query"] == "What is AAPL PE?"
    assert body["conversationId"] == "sess-1"
    assert body["context"]["routeMetadata"]["channel"] == "whatsapp"


@pytest.mark.asyncio
@respx.mock
async def test_forwarder_per_call_bearer_override():
    mock = respx.post(_URL).mock(return_value=httpx.Response(200, json={"response": {"text": "ok"}}))
    fwd = HarnessForwarder(harness_url=_HARNESS, bearer_token="default", rate_limiter=None)
    await fwd.forward("hi", user_id="u1", conversation_id="c1", bearer_token="override-tok")
    assert mock.calls[0].request.headers["Authorization"] == "Bearer override-tok"


@pytest.mark.asyncio
@respx.mock
async def test_forwarder_empty_response_text_returns_empty_string():
    respx.post(_URL).mock(return_value=httpx.Response(200, json={"response": {"text": ""}}))
    fwd = HarnessForwarder(harness_url=_HARNESS, bearer_token="", rate_limiter=None)
    result = await fwd.forward("hi", user_id="u1", conversation_id="c1")
    assert result == ""


@pytest.mark.asyncio
@respx.mock
async def test_forwarder_missing_response_key_returns_empty():
    respx.post(_URL).mock(return_value=httpx.Response(200, json={}))
    fwd = HarnessForwarder(harness_url=_HARNESS, bearer_token="", rate_limiter=None)
    result = await fwd.forward("hi", user_id="u1", conversation_id="c1")
    assert result == ""


@pytest.mark.asyncio
@respx.mock
async def test_forwarder_raises_on_http_error():
    respx.post(_URL).mock(return_value=httpx.Response(500, text="Server Error"))
    fwd = HarnessForwarder(harness_url=_HARNESS, bearer_token="", rate_limiter=None)
    with pytest.raises(httpx.HTTPStatusError):
        await fwd.forward("hi", user_id="u1", conversation_id="c1")


# ─── RateLimiter ──────────────────────────────────────────────────────────────


def test_rate_limiter_allows_within_window():
    rl = RateLimiter(max_requests=3, window_seconds=60)
    assert rl.is_allowed("u1") is True
    assert rl.is_allowed("u1") is True
    assert rl.is_allowed("u1") is True


def test_rate_limiter_blocks_when_exceeded():
    rl = RateLimiter(max_requests=2, window_seconds=60)
    rl.is_allowed("u1")
    rl.is_allowed("u1")
    assert rl.is_allowed("u1") is False


def test_rate_limiter_different_senders_independent():
    rl = RateLimiter(max_requests=1, window_seconds=60)
    rl.is_allowed("u1")
    assert rl.is_allowed("u1") is False
    assert rl.is_allowed("u2") is True  # different sender


def test_rate_limiter_reset_clears_sender():
    rl = RateLimiter(max_requests=1, window_seconds=60)
    rl.is_allowed("u1")
    rl.reset("u1")
    assert rl.is_allowed("u1") is True


def test_rate_limiter_reset_all():
    rl = RateLimiter(max_requests=1, window_seconds=60)
    rl.is_allowed("u1")
    rl.is_allowed("u2")
    rl.reset()
    assert rl.is_allowed("u1") is True
    assert rl.is_allowed("u2") is True


@pytest.mark.asyncio
@respx.mock
async def test_forwarder_raises_rate_limit_error():
    respx.post(_URL).mock(return_value=httpx.Response(200, json={"response": {"text": "ok"}}))
    rl = RateLimiter(max_requests=1, window_seconds=60)
    fwd = HarnessForwarder(harness_url=_HARNESS, bearer_token="", rate_limiter=rl)
    await fwd.forward("first", user_id="u1", conversation_id="c1")
    with pytest.raises(RateLimitError):
        await fwd.forward("second", user_id="u1", conversation_id="c1")


# ─── Gateway imports don't pull in neonize ────────────────────────────────────


def test_gateway_import_no_neonize():
    import sys
    import importlib

    importlib.import_module("ai.gateway")
    importlib.import_module("ai.gateway.http_forwarder")
    importlib.import_module("ai.gateway.whatsapp")
    importlib.import_module("ai.gateway.whatsapp.handlers")
    assert "neonize" not in sys.modules


def test_discord_stub_not_implemented():
    from ai.gateway.discord.bot import DiscordBot

    bot = DiscordBot()
    with pytest.raises(NotImplementedError):
        bot.start()


def test_discord_stub_async_not_implemented():
    import asyncio
    from ai.gateway.discord.bot import DiscordBot

    bot = DiscordBot()
    with pytest.raises(NotImplementedError):
        asyncio.run(bot.start_async())


def test_whatsapp_client_raises_import_error_without_neonize():
    import sys

    # Ensure neonize is NOT in sys.modules (it shouldn't be in CI)
    neonize_mod = sys.modules.pop("neonize", None)
    try:
        from ai.gateway.whatsapp.client import WhatsAppClient

        client = WhatsAppClient()
        with pytest.raises(ImportError, match="neonize"):
            client.start()
    finally:
        if neonize_mod is not None:
            sys.modules["neonize"] = neonize_mod
