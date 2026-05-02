"""Tests for the LLM Council."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from ai.council.base import calculate_aggregate_rankings, parse_ranking_from_text
from ai.council.runner import run_council
from ai.council.v1.council import V1Council
from ai.council.v2.council import V2Council
from ai.memory.para import ParaMemoryLayout
from ai.memory.writer import MemoryWriter
from ai.routes.context import RouteContext
from ai.schemas.agent import CouncilRankingItem, CouncilRunResult, CouncilStageItem

# ─── Fake query transport ─────────────────────────────────────────────────────


class FakeQueryParallel:
    """Fake query function that records calls and returns scripted responses."""

    def __init__(self, responses: dict[str, str | None] | list[dict[str, str | None]]) -> None:
        self.responses = responses
        self.calls: list[tuple[list[str], list[dict[str, str]]]] = []

    async def __call__(self, models: list[str], messages: list[dict[str, str]]) -> dict[str, str | None]:
        self.calls.append((list(models), messages))
        if isinstance(self.responses, list):
            response = self.responses[len(self.calls) - 1]
        else:
            response = self.responses
        return {model: response.get(model, f"Opinion from {model}.") for model in models}


def _make_route_ctx(tmp_path: Path, input_data: dict | None = None, route_metadata: dict | None = None) -> RouteContext:
    layout = ParaMemoryLayout(tmp_path)
    return RouteContext(
        user_id="u1",
        request=SimpleNamespace(context=SimpleNamespace(route_metadata=route_metadata or {})),  # type: ignore[arg-type]
        bearer_token=None,
        input=input_data or {},
        layout=layout,
        writer=MemoryWriter(layout),
        progress=AsyncMock(),
        call_llm=AsyncMock(return_value="llm response"),
    )


def _make_council_run_result(
    *,
    response: str = "Council says: 4.",
    stage1: list[CouncilStageItem] | None = None,
) -> CouncilRunResult:
    return CouncilRunResult(
        version="v1",
        stage1=stage1 or [CouncilStageItem(model="m1", response="M1 view.")],
        stage3=CouncilStageItem(model="judge", response=response),
        metadata={},
    )


# ─── Shared flow unit tests ───────────────────────────────────────────────────


def test_parse_ranking_standard_format():
    text = "Some evaluation.\nFINAL RANKING:\n1. Response A\n2. Response C\n3. Response B"
    parsed = parse_ranking_from_text(text)
    assert parsed == ["Response A", "Response C", "Response B"]


def test_parse_ranking_fallback_no_final_ranking_header():
    text = "Response B is better than Response A."
    parsed = parse_ranking_from_text(text)
    assert "Response B" in parsed
    assert "Response A" in parsed


def test_parse_ranking_empty_text():
    assert parse_ranking_from_text("") == []


def test_parse_ranking_no_labels():
    assert parse_ranking_from_text("No ranking provided.") == []


def test_calculate_aggregate_rankings():
    rankings = [
        CouncilRankingItem(model="judge-a", ranking="", parsed_ranking=["Response B", "Response A"]),
        CouncilRankingItem(model="judge-b", ranking="", parsed_ranking=["Response A", "Response B"]),
    ]
    aggregate = calculate_aggregate_rankings(rankings, {"Response A": "model-a", "Response B": "model-b"})
    assert [ranking.model for ranking in aggregate] == ["model-b", "model-a"]
    assert aggregate[0].average_rank == 1.5


# ─── Version run tests (mocked) ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_v1_run_returns_final_text():
    query_parallel = FakeQueryParallel(
        [
            {
                "model-a": "Opinion A.",
                "model-b": "Opinion B.",
            },
            {"judge": "Synthesised answer."},
        ]
    )
    result = await V1Council(query_parallel=query_parallel).run(
        "What is 2+2?",
        models=["model-a", "model-b"],
        judge_model="judge",
        include_rankings=False,
    )
    assert isinstance(result, CouncilRunResult)
    assert result.stage3 is not None
    assert result.stage3.response == "Synthesised answer."
    assert result.stage3.model == "judge"


@pytest.mark.asyncio
async def test_v1_run_sub_opinions_in_result():
    query_parallel = FakeQueryParallel(
        [
            {
                "model-a": "Opinion A.",
                "model-b": "Opinion B.",
            },
            {"judge": "Final."},
        ]
    )
    result = await V1Council(query_parallel=query_parallel).run(
        "Query",
        models=["model-a", "model-b"],
        judge_model="judge",
        include_rankings=False,
    )
    assert len(result.stage1) == 2
    assert {op.model for op in result.stage1} == {"model-a", "model-b"}


@pytest.mark.asyncio
async def test_v1_run_one_panelist_fails_does_not_abort():
    query_parallel = FakeQueryParallel(
        [
            {
                "model-a": None,
                "model-b": "B opinion.",
            },
            {"judge": "Synthesis."},
        ]
    )
    result = await V1Council(query_parallel=query_parallel).run(
        "Query",
        models=["model-a", "model-b"],
        judge_model="judge",
        include_rankings=False,
    )
    assert result.stage3 is not None
    assert result.stage3.response == "Synthesis."
    assert result.metadata["failed_models"] == ["model-a"]


@pytest.mark.asyncio
async def test_v1_run_all_panelists_fail():
    query_parallel = FakeQueryParallel({"model-a": None, "model-b": None})
    result = await V1Council(query_parallel=query_parallel).run(
        "Query",
        models=["model-a", "model-b"],
        judge_model="judge",
        include_rankings=False,
    )
    assert result.stage3 is not None
    assert result.stage3.response.startswith("All council panelists failed")
    assert result.stage1 == []


@pytest.mark.asyncio
async def test_v1_run_with_rankings():
    ranking_text = "Response A is better.\nFINAL RANKING:\n1. Response A\n2. Response B"
    query_parallel = FakeQueryParallel(
        [
            {
                "model-a": "A opinion.",
                "model-b": "B opinion.",
            },
            {
                "model-a": ranking_text,
                "model-b": ranking_text,
            },
            {"judge": "Final synthesis."},
        ]
    )
    result = await V1Council(query_parallel=query_parallel).run(
        "Query",
        models=["model-a", "model-b"],
        judge_model="judge",
        include_rankings=True,
    )
    assert result.stage3 is not None
    assert result.stage3.response == "Final synthesis."
    assert len(result.stage2) == 2
    assert result.aggregate_rankings


@pytest.mark.asyncio
async def test_v1_run_judge_failure_returns_error_message():
    query_parallel = FakeQueryParallel(
        [
            {"model-a": "Opinion."},
            {"judge": None},
        ]
    )
    result = await V1Council(query_parallel=query_parallel).run(
        "Query",
        models=["model-a"],
        judge_model="judge",
        include_rankings=False,
    )
    assert result.stage3 is not None
    assert "error" in result.stage3.response.lower() or "failed" in result.stage3.response.lower()


@pytest.mark.asyncio
async def test_v2_run_returns_council_result():
    query_parallel = FakeQueryParallel(
        [
            {"model-a": "Opinion A."},
            {"judge": "Final."},
        ]
    )
    result = await V2Council(query_parallel=query_parallel).run(
        "Query",
        models=["model-a"],
        judge_model="judge",
        include_rankings=False,
    )
    assert result.version == "v2"
    assert result.stage3 is not None
    assert result.stage3.response == "Final."


@pytest.mark.asyncio
async def test_runner_dispatches_versions():
    v1_instance = SimpleNamespace(run=AsyncMock(return_value=_make_council_run_result(response="v1")))
    v2_first_instance = SimpleNamespace(run=AsyncMock(return_value=_make_council_run_result(response="v2")))
    v2_second_instance = SimpleNamespace(run=AsyncMock(return_value=_make_council_run_result(response="v2 again")))

    with (
        patch("ai.council.runner.V1Council", side_effect=[v1_instance]) as v1_council_mock,
        patch("ai.council.runner.V2Council", side_effect=[v2_first_instance, v2_second_instance]) as v2_council_mock,
    ):
        result_v1 = await run_council("Q?", version="v1", models=["m1"], judge_model="judge")
        result_v2 = await run_council("Q?", version="v2", models=["m1"], judge_model="judge")
        result_v2_again = await run_council("Q?", version="v2", models=["m1"], judge_model="judge")

    assert result_v1.stage3 is not None
    assert result_v1.stage3.response == "v1"
    assert result_v2.stage3 is not None
    assert result_v2.stage3.response == "v2"
    assert result_v2_again.stage3 is not None
    assert result_v2_again.stage3.response == "v2 again"
    assert v1_council_mock.call_count == 1
    assert v2_council_mock.call_count == 2
    v1_instance.run.assert_awaited_once()
    v2_first_instance.run.assert_awaited_once()
    v2_second_instance.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_runner_unknown_version_raises():
    with pytest.raises(ValueError):
        await run_council("Q?", version="unknown", models=["m1"], judge_model="judge")  # type: ignore[arg-type]


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

    with patch("ai.routes.llm_council.run_council", AsyncMock(return_value=_make_council_run_result())):
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

    with patch(
        "ai.routes.llm_council.run_council",
        AsyncMock(
            return_value=_make_council_run_result(
                response="Final.",
                stage1=[CouncilStageItem(model="m1", response="M1.")],
            )
        ),
    ):
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

    with patch(
        "ai.routes.llm_council.run_council",
        AsyncMock(
            return_value=_make_council_run_result(
                response="Synthesis.",
                stage1=[CouncilStageItem(model="m2", response="M2 opinion.")],
            )
        ),
    ):
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

    with patch("ai.routes.llm_council.run_council", AsyncMock(return_value=_make_council_run_result(response="Final."))):
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


@pytest.mark.asyncio
async def test_llm_council_route_uses_input_version(tmp_path):
    from ai.routes.llm_council import run

    run_council_mock = AsyncMock(return_value=_make_council_run_result(response="Final."))
    with patch("ai.routes.llm_council.run_council", run_council_mock):
        ctx = _make_route_ctx(
            tmp_path,
            {
                "query": "Q?",
                "models": ["m1"],
                "council_version": "v1",
            },
        )
        result = await run(ctx)

    assert result.ok is True
    assert run_council_mock.await_args.kwargs["version"] == "v1"


@pytest.mark.asyncio
async def test_llm_council_route_uses_route_metadata_version(tmp_path):
    from ai.routes.llm_council import run

    run_council_mock = AsyncMock(return_value=_make_council_run_result(response="Final."))
    with patch("ai.routes.llm_council.run_council", run_council_mock):
        ctx = _make_route_ctx(
            tmp_path,
            {
                "query": "Q?",
                "models": ["m1"],
            },
            route_metadata={"council_version": "v1"},
        )
        result = await run(ctx)

    assert result.ok is True
    assert run_council_mock.await_args.kwargs["version"] == "v1"
