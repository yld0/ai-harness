"""V1 council implementation."""

from __future__ import annotations

from ai.council.base import (
    BaseCouncilVersion,
    build_chairman_prompt,
    build_ranking_prompt,
)
from ai.schemas.agent import CouncilRankingItem, CouncilStageItem


class V1Council(BaseCouncilVersion):
    """Council v1: plain three-stage OpenRouter council."""

    version = "v1"
    all_panelists_failed_text = "All council panelists failed to respond."
    judge_failed_text = "Council error: judge model failed to synthesise a response."

    async def opinions(self, query: str, models: list[str]) -> dict[str, str | None]:
        """Collect stage-one opinions."""
        return await self.query_parallel(models, [{"role": "user", "content": query}])

    async def rank(
        self,
        query: str,
        models: list[str],
        stage1: list[CouncilStageItem],
    ) -> dict[str, str | None]:
        """Collect stage-two peer rankings."""
        return await self.query_parallel(models, [{"role": "user", "content": build_ranking_prompt(query, stage1)}])

    async def final_review(
        self,
        query: str,
        judge_model: str,
        stage1: list[CouncilStageItem],
        stage2: list[CouncilRankingItem],
    ) -> str | None:
        """Collect the final judge synthesis."""
        response = await self.query_parallel(
            [judge_model],
            [{"role": "user", "content": build_chairman_prompt(query, stage1, stage2)}],
        )
        return response.get(judge_model)
