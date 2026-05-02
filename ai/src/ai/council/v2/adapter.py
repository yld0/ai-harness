"""Adapt ai-master-style council tuples to the shared council schema."""

from __future__ import annotations

from typing import Any

from ai.schemas.agent import AggregateRanking, CouncilRankingItem, CouncilRunResult, CouncilStageItem


def to_council_run_result(
    stage1: list[dict[str, Any]],
    stage2: list[dict[str, Any]],
    stage3_result: dict[str, Any],
    metadata: dict[str, Any],
) -> CouncilRunResult:
    """Convert v2's tuple return value to the version-agnostic schema."""
    aggregate_rankings = metadata.get("aggregate_rankings", [])
    result_metadata = {key: value for key, value in metadata.items() if key != "aggregate_rankings"}
    stage3 = None
    if stage3_result.get("model") != "error":
        stage3 = CouncilStageItem(
            model=stage3_result["model"],
            response=stage3_result["response"],
        )

    return CouncilRunResult(
        version="v2",
        stage1=[
            CouncilStageItem(model=result["model"], response=result["response"])
            for result in stage1
        ],
        stage2=[
            CouncilRankingItem(
                model=result["model"],
                ranking=result["ranking"],
                parsed_ranking=result.get("parsed_ranking", []),
            )
            for result in stage2
        ],
        stage3=stage3,
        aggregate_rankings=[AggregateRanking(**ranking) for ranking in aggregate_rankings],
        metadata=result_metadata,
    )
