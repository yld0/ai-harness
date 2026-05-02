"""V2 council implementation with ai-master-style progress events."""

from __future__ import annotations

from ai.api.send import send_ws_partial, send_ws_task_update
from ai.council.base import (
    BaseCouncilVersion,
    QueryParallel,
    build_chairman_prompt,
    build_ranking_prompt,
    default_query_parallel,
)
from ai.schemas.agent import (
    AggregateRanking,
    ChatProviderTabsComponent,
    ChatResponse,
    CouncilRankingItem,
    CouncilStageItem,
    ProviderTab,
    TaskItemUpdate,
    TaskUpdateMessage,
)


def rankings_to_text(aggregate_rankings: list[AggregateRanking]) -> str:
    """Render aggregate rankings for progress updates."""
    return "\n".join(f"{ranking.model} ranked {ranking.average_rank} with {ranking.rankings_count} rankings" for ranking in aggregate_rankings)


class V2Council(BaseCouncilVersion):
    """Council v2: ai-master-style presentation around the shared lifecycle."""

    version = "v2"
    all_panelists_failed_text = "All models failed to respond. Please try again."
    judge_failed_text = "Error: Unable to generate final synthesis."

    def __init__(self, query_parallel: QueryParallel | None = None) -> None:
        self.query_parallel = query_parallel or default_query_parallel
        self.task_s1 = TaskUpdateMessage(task_id="stage1", default_open=True, title="Stage 1: Collecting responses", items=[])
        self.task_s2 = TaskUpdateMessage(task_id="stage2", default_open=True, title="Stage 2: Peer rankings", items=[])
        self.task_s3 = TaskUpdateMessage(task_id="stage3", default_open=True, title="Stage 3: Final synthesis", items=[])

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

    async def on_stage_start(self, stage: str) -> None:
        """Send ai-master-style stage task updates."""
        task = {"stage1": self.task_s1, "stage2": self.task_s2, "stage3": self.task_s3}[stage]
        await send_ws_task_update(task)

    async def on_opinions_done(self, stage1: list[CouncilStageItem], failed_models: list[str]) -> None:
        """Send provider tabs after opinions are collected."""
        if not stage1:
            self.task_s1.items.append(TaskItemUpdate(type="item", content="All models failed to respond."))
            await send_ws_task_update(self.task_s1)
            return

        await send_ws_partial(
            ChatResponse(
                text="Stage 1: Individual responses",
                extra_components=[
                    ChatProviderTabsComponent(
                        default_open=False,
                        providers=[ProviderTab(model=result.model, response=result.response) for result in stage1],
                    ),
                ],
            )
        )

    async def on_rank_done(self, rankings: list[CouncilRankingItem], aggregate_rankings: list[AggregateRanking]) -> None:
        """Send aggregate ranking progress updates."""
        self.task_s2.items.append(TaskItemUpdate(type="item", content=rankings_to_text(aggregate_rankings)))
        await send_ws_task_update(self.task_s2)
        self.task_s2.items.append(TaskItemUpdate(type="item", content=f"{', '.join([ranking.model for ranking in rankings])} ranked"))
        await send_ws_task_update(self.task_s2)

    async def on_final_done(self, judge_model: str, final_text: str) -> None:
        """Send final synthesis progress update."""
        self.task_s3.items.append(TaskItemUpdate(type="item", content=f"{judge_model} synthesized"))
        await send_ws_task_update(self.task_s3)
