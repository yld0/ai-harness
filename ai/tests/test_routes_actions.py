"""Tests for action route handlers: catchup, market-catchup, tldr-news, recent-earnings."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from ai.memory.para import ParaMemoryLayout
from ai.memory.writer import MemoryWriter
from ai.routes.context import RouteContext


def _make_ctx(tmp_path: Path, input_data: dict | None = None, llm_return: str = "LLM response") -> RouteContext:
    layout = ParaMemoryLayout(tmp_path)
    layout.ensure_user_layout("u1")
    return RouteContext(
        user_id="u1",
        request=None,  # type: ignore[arg-type]
        bearer_token=None,
        input=input_data or {},
        layout=layout,
        writer=MemoryWriter(layout),
        progress=AsyncMock(),
        call_llm=AsyncMock(return_value=llm_return),
    )


# ─── actions-catchup ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_catchup_returns_llm_text(tmp_path):
    from ai.routes.actions_catchup import run

    ctx = _make_ctx(tmp_path, llm_return="• Nothing happened\n• All quiet")
    result = await run(ctx)
    assert result.ok is True
    assert "Nothing happened" in result.text


@pytest.mark.asyncio
async def test_catchup_includes_system_hint(tmp_path):
    from ai.routes.actions_catchup import run

    ctx = _make_ctx(tmp_path, {"system_hint": "Focus on tech stocks."})
    result = await run(ctx)
    assert result.ok is True
    ctx.call_llm.assert_awaited_once()
    called_prompt = ctx.call_llm.call_args[0][0]
    assert "Focus on tech stocks." in called_prompt


@pytest.mark.asyncio
async def test_catchup_error_returns_not_ok(tmp_path):
    from ai.routes.actions_catchup import run

    ctx = _make_ctx(tmp_path)
    ctx.call_llm.side_effect = RuntimeError("timeout")
    result = await run(ctx)
    assert result.ok is False
    assert result.error == "llm_error"


@pytest.mark.asyncio
async def test_catchup_metadata_route(tmp_path):
    from ai.routes.actions_catchup import run

    ctx = _make_ctx(tmp_path)
    result = await run(ctx)
    assert result.metadata.get("route") == "actions-catchup"


# ─── actions-market-catchup ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_market_catchup_ok(tmp_path):
    from ai.routes.actions_market_catchup import run

    ctx = _make_ctx(tmp_path, llm_return="Market: flat\nWatchlist: nothing notable")
    result = await run(ctx)
    assert result.ok is True
    assert "Market" in result.text


@pytest.mark.asyncio
async def test_market_catchup_error(tmp_path):
    from ai.routes.actions_market_catchup import run

    ctx = _make_ctx(tmp_path)
    ctx.call_llm.side_effect = ConnectionError("no network")
    result = await run(ctx)
    assert result.ok is False
    assert result.error == "llm_error"


# ─── action-tldr-news ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tldr_news_default(tmp_path):
    from ai.routes.action_tldr_news import run

    ctx = _make_ctx(tmp_path, llm_return="1. Big headline. Context.")
    result = await run(ctx)
    assert result.ok is True
    assert "headline" in result.text.lower()


@pytest.mark.asyncio
async def test_tldr_news_topic_filter(tmp_path):
    from ai.routes.action_tldr_news import run

    ctx = _make_ctx(tmp_path, {"topics": ["AI", "crypto"], "max_items": 3})
    result = await run(ctx)
    assert result.ok is True
    assert result.metadata["topics"] == ["AI", "crypto"]
    assert result.metadata["max_items"] == 3


@pytest.mark.asyncio
async def test_tldr_news_topic_in_prompt(tmp_path):
    from ai.routes.action_tldr_news import run

    ctx = _make_ctx(tmp_path, {"topics": ["energy"]})
    await run(ctx)
    called_prompt = ctx.call_llm.call_args[0][0]
    assert "energy" in called_prompt


@pytest.mark.asyncio
async def test_tldr_news_error(tmp_path):
    from ai.routes.action_tldr_news import run

    ctx = _make_ctx(tmp_path)
    ctx.call_llm.side_effect = ValueError("bad request")
    result = await run(ctx)
    assert result.ok is False
    assert result.error == "llm_error"


# ─── actions-recent-earnings ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recent_earnings_ok(tmp_path):
    from ai.routes.actions_recent_earnings import run

    ctx = _make_ctx(tmp_path, llm_return="AAPL: Beat EPS by $0.10")
    result = await run(ctx)
    assert result.ok is True
    assert "AAPL" in result.text


@pytest.mark.asyncio
async def test_recent_earnings_ticker_clause(tmp_path):
    from ai.routes.actions_recent_earnings import run

    ctx = _make_ctx(tmp_path, {"tickers": ["MSFT", "GOOG"], "days_back": 14})
    await run(ctx)
    called_prompt = ctx.call_llm.call_args[0][0]
    assert "MSFT" in called_prompt
    assert "GOOG" in called_prompt
    assert "14" in called_prompt


@pytest.mark.asyncio
async def test_recent_earnings_metadata(tmp_path):
    from ai.routes.actions_recent_earnings import run

    ctx = _make_ctx(tmp_path, {"tickers": ["TSLA"], "days_back": 3})
    result = await run(ctx)
    assert result.metadata["tickers"] == ["TSLA"]
    assert result.metadata["days_back"] == 3


@pytest.mark.asyncio
async def test_recent_earnings_error(tmp_path):
    from ai.routes.actions_recent_earnings import run

    ctx = _make_ctx(tmp_path)
    ctx.call_llm.side_effect = TimeoutError("llm timeout")
    result = await run(ctx)
    assert result.ok is False
    assert result.error == "llm_error"
