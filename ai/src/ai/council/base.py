"""Abstract council lifecycle and shared council flow helpers."""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Awaitable, Callable, Sequence
from typing import Literal

from ai.council.openrouter import query_models_parallel, response_texts
from ai.schemas.agent import AggregateRanking, CouncilRankingItem, CouncilRunResult, CouncilStageItem

CouncilVersionName = Literal["v1", "v2"]
QueryParallel = Callable[[Sequence[str], list[dict[str, str]]], Awaitable[dict[str, str | None]]]

logger = logging.getLogger(__name__)


RANKING_PROMPT = """\
You are evaluating different responses to the following question:

Question: {query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

CHAIRMAN_PROMPT = """\
You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: {query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""


async def default_query_parallel(models: Sequence[str], messages: list[dict[str, str]]) -> dict[str, str | None]:
    """Query OpenRouter and return plain response text by model."""
    return response_texts(await query_models_parallel(models, messages))


def labels_for_stage(stage1: list[CouncilStageItem]) -> dict[str, str]:
    """Return anonymous response label to model mapping for stage-one results."""
    labels = [chr(65 + index) for index in range(len(stage1))]
    return {f"Response {label}": result.model for label, result in zip(labels, stage1)}


def stage_responses_text(stage1: list[CouncilStageItem]) -> str:
    """Render stage-one responses with anonymous labels."""
    labels = [chr(65 + index) for index in range(len(stage1))]
    return "\n\n".join(f"Response {label}:\n{result.response}" for label, result in zip(labels, stage1))


def build_ranking_prompt(query: str, stage1: list[CouncilStageItem]) -> str:
    """Build the peer-ranking prompt."""
    return RANKING_PROMPT.format(query=query, responses_text=stage_responses_text(stage1))


def build_chairman_prompt(query: str, stage1: list[CouncilStageItem], stage2: list[CouncilRankingItem]) -> str:
    """Build the final synthesis prompt."""
    stage1_text = "\n\n".join(f"Model: {result.model}\nResponse: {result.response}" for result in stage1)
    stage2_text = "\n\n".join(f"Model: {result.model}\nRanking: {result.ranking}" for result in stage2)
    return CHAIRMAN_PROMPT.format(query=query, stage1_text=stage1_text, stage2_text=stage2_text)


def parse_ranking_from_text(ranking_text: str) -> list[str]:
    """Parse response labels from a model's ranking text."""
    if "FINAL RANKING:" in ranking_text:
        ranking_section = ranking_text.split("FINAL RANKING:", 1)[1]
        numbered_matches = re.findall(r"\d+\.\s*(Response [A-Z])", ranking_section)
        if numbered_matches:
            return numbered_matches
        return re.findall(r"Response [A-Z]", ranking_section)
    return re.findall(r"Response [A-Z]", ranking_text)


def calculate_aggregate_rankings(
    rankings: list[CouncilRankingItem],
    label_to_model: dict[str, str],
) -> list[AggregateRanking]:
    """Calculate average ranks across peer rankings."""
    model_positions: dict[str, list[int]] = defaultdict(list)
    for ranking in rankings:
        for position, label in enumerate(ranking.parsed_ranking, start=1):
            model_name = label_to_model.get(label)
            if model_name:
                model_positions[model_name].append(position)

    aggregate = [
        AggregateRanking(
            model=model,
            average_rank=round(sum(positions) / len(positions), 2),
            rankings_count=len(positions),
        )
        for model, positions in model_positions.items()
        if positions
    ]
    aggregate.sort(key=lambda ranking: ranking.average_rank)
    return aggregate


def build_result(
    *,
    version: CouncilVersionName,
    stage1: list[CouncilStageItem],
    stage2: list[CouncilRankingItem],
    judge_model: str,
    final_text: str,
    aggregate_rankings: list[AggregateRanking] | None = None,
    metadata: dict[str, object] | None = None,
) -> CouncilRunResult:
    """Build the version-agnostic council result."""
    return CouncilRunResult(
        version=version,
        stage1=stage1,
        stage2=stage2,
        stage3=CouncilStageItem(model=judge_model, response=final_text),
        aggregate_rankings=aggregate_rankings or [],
        metadata=metadata or {},
    )


class BaseCouncilVersion(ABC):
    """ Template for a three-stage council implementation. """

    version: CouncilVersionName

    all_panelists_failed_text = "All council panelists failed to respond."
    judge_failed_text = "Council error: judge model failed to synthesise a response."

    async def run(
        self,
        query: str,
        *,
        models: list[str],
        judge_model: str,
        include_rankings: bool = True,
        no_of_council: int | None = None,
    ) -> CouncilRunResult:
        """Run the invariant council lifecycle for this version."""
        council_models = models[:no_of_council] if no_of_council is not None else models



        # Stage 1: Collect stage-one opinions.

        await self.on_stage_start("stage1")
        opinion_responses = await self.opinions(query, council_models)
        stage1 = [CouncilStageItem(model=model, response=response) for model, response in opinion_responses.items() if response is not None]
        failed_models = [model for model, response in opinion_responses.items() if response is None]
        await self.on_opinions_done(stage1, failed_models)

        if not stage1:
            logger.warning("No stage-one opinions collected, returning failed result")
            return build_result(
                version=self.version,
                stage1=[],
                stage2=[],
                judge_model=judge_model,
                final_text=self.all_panelists_failed_text,
                metadata={"failed_models": failed_models},
            )








        stage2: list[CouncilRankingItem] = []
        label_to_model: dict[str, str] = {}
        aggregate_rankings: list[AggregateRanking] = []
        if include_rankings and len(stage1) > 1:
            await self.on_stage_start("stage2")
            label_to_model = labels_for_stage(stage1)
            ranking_responses = await self.rank(query, council_models, stage1)
            stage2 = [
                CouncilRankingItem(model=model, ranking=ranking, parsed_ranking=parse_ranking_from_text(ranking))
                for model, ranking in ranking_responses.items()
                if ranking is not None
            ]
            aggregate_rankings = calculate_aggregate_rankings(stage2, label_to_model)
            await self.on_rank_done(stage2, aggregate_rankings)

        await self.on_stage_start("stage3")
        final_text = await self.final_review(query, judge_model, stage1, stage2)
        final_text = final_text or self.judge_failed_text
        await self.on_final_done(judge_model, final_text)
        return build_result(
            version=self.version,
            stage1=stage1,
            stage2=stage2,
            judge_model=judge_model,
            final_text=final_text,
            aggregate_rankings=aggregate_rankings,
            metadata={"label_to_model": label_to_model, "failed_models": failed_models},
        )

    @abstractmethod
    async def opinions(self, query: str, models: list[str]) -> dict[str, str | None]:
        """ Stage one: Collect stage-one opinions. """
        ...

    @abstractmethod
    async def rank(
        self, query: str, models: list[str], stage1: list[CouncilStageItem]) -> dict[str, str | None]:
        """ Stage two: Collect stage-two peer rankings. """
        ...

    @abstractmethod
    async def final_review(
        self, query: str, judge_model: str, stage1: list[CouncilStageItem], stage2: list[CouncilRankingItem],
    ) -> str | None:
        """ Stage three: Collect the final judge synthesis. """
        ...

    async def on_stage_start(self, stage: str) -> None:
        """Hook called before each stage starts."""

    async def on_opinions_done(self, stage1: list[CouncilStageItem], failed_models: list[str]) -> None:
        """ Hook called after stage one finishes. """
        ...

    async def on_rank_done(self, rankings: list[CouncilRankingItem], aggregate_rankings: list[AggregateRanking]) -> None:
        """ Hook called after stage two finishes. """
        ...

    async def on_final_done(self, judge_model: str, final_text: str) -> None:
        """ Hook called after stage three finishes. """
        ...
