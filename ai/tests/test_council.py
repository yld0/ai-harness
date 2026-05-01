"""Tests for the LLM Council (Phase 15).

All HTTP calls are mocked via a fake CouncilClient so tests run offline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai.council.client import CouncilClient
from ai.council.council import _parse_ranking, run_council
from ai.council.types import CouncilOpinion, CouncilResult
from ai.memory.para import ParaMemoryLayout
from ai.memory.writer import MemoryWriter
from ai.routes.context import RouteContext

# ─── Fake client ──────────────────────────────────────────────────────────────


class FakeCouncilClient:
    """Synchronous-style fake that records calls and returns scripted responses."""

    def __init__(self, responses: dict[str, str | None] | None = None) -> None:
        # responses: {model: text_or_None}
        self._responses: dict[str, str | None] = responses or {}
        self.queries: list[tuple[str, list]] = []  # (model, messages)

    async def query(self, model: str, messages: list) -> Optional[str]:
        self.queries.append((model, messages))
        return self._responses.get(model, f"Opinion from {model}.")

    async def query_parallel(self, models: list[str], messages: list) -> dict[str, Optional[str]]:
        import asyncio

        results = await asyncio.gather(*[self.query(m, messages) for m in models])
        return dict(zip(models, results))


def _make_route_ctx(tmp_path: Path, input_data: dict | None = None) -> RouteContext:
    layout = ParaMemoryLayout(tmp_path)
    return RouteContext(
        user_id="u1",
        request=None,  # type: ignore[arg-type]
        bearer_token=None,
        input=input_data or {},
        layout=layout,
        writer=MemoryWriter(layout),
        progress=AsyncMock(),
        call_llm=AsyncMock(return_value="llm response"),
    )


# ─── CouncilClient unit tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_client_returns_none_without_api_key():
    client = CouncilClient(api_key="")
    result = await client.query("some/model", [{"role": "user", "content": "hi"}])
    assert result is None


@pytest.mark.asyncio
async def test_client_query_parallel_returns_dict():
    fake = FakeCouncilClient({"m1": "resp1", "m2": "resp2"})
    result = await fake.query_parallel(["m1", "m2"], [{"role": "user", "content": "q"}])
    assert result == {"m1": "resp1", "m2": "resp2"}


@pytest.mark.asyncio
async def test_client_parallel_none_for_failed_model():
    fake = FakeCouncilClient({"m1": None, "m2": "ok"})
    result = await fake.query_parallel(["m1", "m2"], [])
    assert result["m1"] is None
    assert result["m2"] == "ok"


# ─── _parse_ranking unit tests ────────────────────────────────────────────────


def test_parse_ranking_standard_format():
    text = "Some evaluation.\nFINAL RANKING:\n1. Response A\n2. Response C\n3. Response B"
    parsed = _parse_ranking(text)
    assert parsed == ["Response A", "Response C", "Response B"]


def test_parse_ranking_fallback_no_final_ranking_header():
    text = "Response B is better than Response A."
    parsed = _parse_ranking(text)
    assert "Response B" in parsed
    assert "Response A" in parsed


def test_parse_ranking_empty_text():
    assert _parse_ranking("") == []


def test_parse_ranking_no_labels():
    assert _parse_ranking("No ranking provided.") == []


# ─── run_council integration tests (mocked) ───────────────────────────────────


@pytest.mark.asyncio
async def test_run_council_returns_final_text():
    client = FakeCouncilClient(
        {
            "model-a": "Opinion A.",
            "model-b": "Opinion B.",
            "judge": "Synthesised answer.",
        }
    )
    result = await run_council(
        "What is 2+2?",
        models=["model-a", "model-b"],
        judge_model="judge",
        client=client,
        include_rankings=False,
    )
    assert isinstance(result, CouncilResult)
    assert result.final_text == "Synthesised answer."
    assert result.judge_model == "judge"


@pytest.mark.asyncio
async def test_run_council_sub_opinions_in_result():
    client = FakeCouncilClient(
        {
            "model-a": "Opinion A.",
            "model-b": "Opinion B.",
            "judge": "Final.",
        }
    )
    result = await run_council(
        "Query",
        models=["model-a", "model-b"],
        judge_model="judge",
        client=client,
        include_rankings=False,
    )
    assert len(result.opinions) == 2
    models_seen = {op.model for op in result.opinions}
    assert "model-a" in models_seen
    assert "model-b" in models_seen


@pytest.mark.asyncio
async def test_run_council_one_panelist_fails_does_not_abort():
    client = FakeCouncilClient(
        {
            "model-a": None,  # failure
            "model-b": "B opinion.",
            "judge": "Synthesis.",
        }
    )
    result = await run_council(
        "Query",
        models=["model-a", "model-b"],
        judge_model="judge",
        client=client,
        include_rankings=False,
    )
    assert result.final_text == "Synthesis."
    # model-a is marked failed
    failed = [op for op in result.opinions if op.failed]
    assert any(op.model == "model-a" for op in failed)


@pytest.mark.asyncio
async def test_run_council_all_panelists_fail():
    client = FakeCouncilClient({"model-a": None, "model-b": None})
    result = await run_council(
        "Query",
        models=["model-a", "model-b"],
        judge_model="judge",
        client=client,
        include_rankings=False,
    )
    assert result.final_text.startswith("All council panelists failed")
    assert all(op.failed for op in result.opinions)


@pytest.mark.asyncio
async def test_run_council_with_rankings():
    ranking_text = "Response A is better.\nFINAL RANKING:\n1. Response A\n2. Response B"
    client = FakeCouncilClient(
        {
            "model-a": "A opinion.",
            "model-b": "B opinion.",
            "judge": "Final synthesis.",
        }
    )
    # Override parallel to return ranking text for ranking phase
    original_parallel = client.query_parallel
    call_count = [0]

    async def parallel_side_effect(models, messages):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call = stage 1 opinions
            return {m: f"{m} opinion." for m in models}
        # Second call = stage 2 rankings
        return {m: ranking_text for m in models}

    client.query_parallel = parallel_side_effect

    result = await run_council(
        "Query",
        models=["model-a", "model-b"],
        judge_model="judge",
        client=client,
        include_rankings=True,
    )
    assert result.final_text == "Final synthesis."
    # Rankings should have been collected
    assert len(result.rankings) == 2


@pytest.mark.asyncio
async def test_run_council_judge_failure_returns_error_message():
    client = FakeCouncilClient(
        {
            "model-a": "Opinion.",
            "judge": None,  # judge fails
        }
    )
    result = await run_council(
        "Query",
        models=["model-a"],
        judge_model="judge",
        client=client,
        include_rankings=False,
    )
    assert "error" in result.final_text.lower() or "failed" in result.final_text.lower()


# ─── Route handler tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_llm_council_route_missing_query(tmp_path):
    from ai.routes.llm_council import run

    ctx = _make_route_ctx(tmp_path, {})
    result = await run(ctx)
    assert result.ok is False
    assert result.error == "missing_input"


@pytest.mark.asyncio
async def test_llm_council_route_no_models(tmp_path):
    from ai.routes.llm_council import run

    ctx = _make_route_ctx(tmp_path, {"query": "What is 2+2?", "models": []})
    result = await run(ctx)
    assert result.ok is False
    assert result.error == "no_models"


@pytest.mark.asyncio
async def test_llm_council_route_returns_final_text(tmp_path):
    from ai.routes.llm_council import run

    fake = FakeCouncilClient({"m1": "M1 view.", "m2": "M2 view.", "judge": "Council says: 4."})
    with patch("ai.routes.llm_council.CouncilClient", return_value=fake):
        ctx = _make_route_ctx(
            tmp_path,
            {
                "query": "What is 2+2?",
                "models": ["m1", "m2"],
                "judge_model": "judge",
                "include_rankings": False,
            },
        )
        result = await run(ctx)

    assert result.ok is True
    assert "4" in result.text


@pytest.mark.asyncio
async def test_llm_council_route_metadata_has_opinions(tmp_path):
    from ai.routes.llm_council import run

    fake = FakeCouncilClient({"m1": "M1.", "judge": "Final."})
    with patch("ai.routes.llm_council.CouncilClient", return_value=fake):
        ctx = _make_route_ctx(
            tmp_path,
            {
                "query": "Q?",
                "models": ["m1"],
                "judge_model": "judge",
                "include_rankings": False,
            },
        )
        result = await run(ctx)

    assert "opinions" in result.metadata
    assert len(result.metadata["opinions"]) == 1
    assert result.metadata["opinions"][0]["model"] == "m1"


@pytest.mark.asyncio
async def test_llm_council_route_one_failure_still_ok(tmp_path):
    from ai.routes.llm_council import run

    fake = FakeCouncilClient({"m1": None, "m2": "M2 opinion.", "judge": "Synthesis."})
    with patch("ai.routes.llm_council.CouncilClient", return_value=fake):
        ctx = _make_route_ctx(
            tmp_path,
            {
                "query": "Q?",
                "models": ["m1", "m2"],
                "judge_model": "judge",
                "include_rankings": False,
            },
        )
        result = await run(ctx)

    assert result.ok is True
    assert result.metadata["panelists_succeeded"] == 1


@pytest.mark.asyncio
async def test_llm_council_route_models_as_csv_string(tmp_path):
    from ai.routes.llm_council import run

    fake = FakeCouncilClient({"m1": "M1.", "m2": "M2.", "judge": "Final."})
    with patch("ai.routes.llm_council.CouncilClient", return_value=fake):
        ctx = _make_route_ctx(
            tmp_path,
            {
                "query": "Q?",
                "models": "m1,m2",
                "judge_model": "judge",
                "include_rankings": False,
            },
        )
        result = await run(ctx)

    assert result.ok is True
