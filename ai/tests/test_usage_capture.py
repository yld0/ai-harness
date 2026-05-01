from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import ai.usage.capture as usage_capture
from ai.context import BEARER_TOKEN, CONVERSATION_ID, REQUEST_ID
from ai.usage.capture import (
    _extract_usage,
    capture,
    get_capture_by_request_id,
    get_latest_captures,
    get_request_captures,
)


@pytest.fixture(autouse=True)
def _clear_usage_request_cache() -> None:
    """Isolate tests that touch the module-level per-request cache."""
    usage_capture._request_cache.clear()
    usage_capture._request_order.clear()
    yield
    usage_capture._request_cache.clear()
    usage_capture._request_order.clear()


# ── _extract_usage ────────────────────────────────────────────────────────────


def _mock_response(usage: dict | None, model: str = "gemini-flash") -> MagicMock:
    r = MagicMock()
    r.model = model
    r.usage = usage
    return r


def test_extract_usage_returns_none_for_empty_usage() -> None:
    assert _extract_usage(_mock_response(None)) is None
    assert _extract_usage(_mock_response({})) is None


def test_extract_usage_returns_none_for_all_zero_tokens() -> None:
    assert _extract_usage(_mock_response({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})) is None


def test_extract_usage_basic() -> None:
    result = _extract_usage(
        _mock_response(
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            model="gemini-2.5-flash",
        )
    )
    assert result is not None
    assert result["prompt_tokens"] == 10
    assert result["completion_tokens"] == 5
    assert result["total_tokens"] == 15
    assert result["model_id"] == "gemini-2.5-flash"
    assert result["thinking_tokens"] == 0
    assert result["cached_tokens"] == 0


def test_extract_usage_optional_fields() -> None:
    result = _extract_usage(
        _mock_response(
            {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "thinking_tokens": 20,
                "cached_tokens": 10,
            }
        )
    )
    assert result is not None
    assert result["thinking_tokens"] == 20
    assert result["cached_tokens"] == 10


def test_extract_usage_derives_total_when_missing() -> None:
    result = _extract_usage(_mock_response({"prompt_tokens": 8, "completion_tokens": 4}))
    assert result is not None
    assert result["total_tokens"] == 12


# ── capture() — no-op without context ─────────────────────────────────────────


async def test_capture_noop_when_no_bearer_token() -> None:
    """capture() must not call AIClient when bearer_token ContextVar is unset."""
    response = _mock_response({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
    with patch("ai.usage.capture._ai_client") as mock_client_fn:
        await capture(response)
        mock_client_fn.assert_not_called()


async def test_capture_noop_when_no_conversation_id() -> None:
    """capture() must not call AIClient when conversation_id ContextVar is unset."""
    tok = BEARER_TOKEN.set("test-token")
    try:
        response = _mock_response({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
        with patch("ai.usage.capture._ai_client") as mock_client_fn:
            await capture(response)
            mock_client_fn.assert_not_called()
    finally:
        BEARER_TOKEN.reset(tok)


# ── capture() — calls AIClient when context is set ───────────────────────────


async def test_capture_calls_ai_client_when_context_set() -> None:
    bearer_token_ctx = BEARER_TOKEN.set("tok-abc")
    conversation_id_ctx = CONVERSATION_ID.set("conv-xyz")
    try:
        mock_client = AsyncMock()
        mock_client.capture_usage = AsyncMock(return_value=True)
        with patch("ai.usage.capture._ai_client", return_value=mock_client):
            response = _mock_response(
                {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
                model="gemini-2.5-flash",
            )
            await capture(response)
            mock_client.capture_usage.assert_awaited_once()
            call_kwargs = mock_client.capture_usage.call_args.kwargs
            assert call_kwargs["bearer_token"] == "tok-abc"
            assert call_kwargs["conversation_id"] == "conv-xyz"
            assert call_kwargs["model_id"] == "gemini-2.5-flash"
            assert call_kwargs["prompt_tokens"] == 100
            assert call_kwargs["completion_tokens"] == 50
            assert call_kwargs["total_tokens"] == 150
    finally:
        BEARER_TOKEN.reset(bearer_token_ctx)
        CONVERSATION_ID.reset(conversation_id_ctx)


async def test_capture_noop_for_zero_usage_even_with_context() -> None:
    bearer_token_ctx = BEARER_TOKEN.set("tok")
    conversation_id_ctx = CONVERSATION_ID.set("conv-123")
    try:
        mock_client = AsyncMock()
        with patch("ai.usage.capture._ai_client", return_value=mock_client):
            await capture(_mock_response(None))
            mock_client.capture_usage.assert_not_called()
    finally:
        BEARER_TOKEN.reset(bearer_token_ctx)
        CONVERSATION_ID.reset(conversation_id_ctx)


async def test_capture_swallows_gql_exception() -> None:
    """GQL failures must not propagate — usage capture is best-effort."""
    bearer_token_ctx = BEARER_TOKEN.set("tok")
    conversation_id_ctx = CONVERSATION_ID.set("conv-err")
    try:
        mock_client = AsyncMock()
        mock_client.capture_usage = AsyncMock(side_effect=RuntimeError("network down"))
        with patch("ai.usage.capture._ai_client", return_value=mock_client):
            response = _mock_response({"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})
            await capture(response)
    finally:
        BEARER_TOKEN.reset(bearer_token_ctx)
        CONVERSATION_ID.reset(conversation_id_ctx)


# ── request cache (per request_id) ───────────────────────────────────────────


async def test_capture_updates_request_cache_when_request_id_set() -> None:
    bearer_token_ctx = BEARER_TOKEN.set("bearer-1")
    conversation_id_ctx = CONVERSATION_ID.set("conv-1")
    request_id_ctx = REQUEST_ID.set("req-100")
    try:
        mock_client = AsyncMock()
        mock_client.capture_usage = AsyncMock(return_value=True)
        with patch("ai.usage.capture._ai_client", return_value=mock_client):
            await capture(
                _mock_response(
                    {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
                    model="m-1",
                )
            )
        entry = get_capture_by_request_id("req-100")
        assert entry is not None
        assert entry["request_id"] == "req-100"
        assert entry["prompt_tokens"] == 2
        assert entry["completion_tokens"] == 3
        assert entry["total_tokens"] == 5
        assert len(get_request_captures()) == 1
        assert get_latest_captures(n=1)[0]["request_id"] == "req-100"
    finally:
        REQUEST_ID.reset(request_id_ctx)
        BEARER_TOKEN.reset(bearer_token_ctx)
        CONVERSATION_ID.reset(conversation_id_ctx)


async def test_request_cache_aggregates_same_request_id() -> None:
    bearer_token_ctx = BEARER_TOKEN.set("b")
    conversation_id_ctx = CONVERSATION_ID.set("c")
    request_id_ctx = REQUEST_ID.set("req-agg")
    try:
        mock_client = AsyncMock()
        mock_client.capture_usage = AsyncMock(return_value=True)
        with patch("ai.usage.capture._ai_client", return_value=mock_client):
            await capture(
                _mock_response(
                    {
                        "prompt_tokens": 10,
                        "completion_tokens": 0,
                        "total_tokens": 10,
                    }
                )
            )
            await capture(
                _mock_response(
                    {
                        "prompt_tokens": 0,
                        "completion_tokens": 5,
                        "total_tokens": 5,
                    }
                )
            )
        entry = get_capture_by_request_id("req-agg")
        assert entry is not None
        assert entry["prompt_tokens"] == 10
        assert entry["completion_tokens"] == 5
        assert entry["total_tokens"] == 15
    finally:
        REQUEST_ID.reset(request_id_ctx)
        BEARER_TOKEN.reset(bearer_token_ctx)
        CONVERSATION_ID.reset(conversation_id_ctx)
