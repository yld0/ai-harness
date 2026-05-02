"""Adapt v1 council dataclasses to the shared council schema."""

from __future__ import annotations

from ai.council.v1.types import CouncilResult
from ai.schemas.agent import AggregateRanking, CouncilRankingItem, CouncilRunResult, CouncilStageItem


def to_council_run_result(result: CouncilResult) -> CouncilRunResult:
    """Convert a v1 ``CouncilResult`` to the version-agnostic schema."""
    return CouncilRunResult(
        version="v1",
        stage1=[
            CouncilStageItem(model=op.model, response=op.text)
            for op in result.opinions
            if not op.failed
        ],
        stage2=[
            CouncilRankingItem(model=ranking.model, ranking=ranking.raw, parsed_ranking=ranking.parsed)
            for ranking in result.rankings
            if not ranking.failed
        ],
        stage3=CouncilStageItem(model=result.judge_model, response=result.final_text),
        aggregate_rankings=[AggregateRanking(**ranking) for ranking in result.aggregate_rankings],
        metadata=result.metadata,
    )
