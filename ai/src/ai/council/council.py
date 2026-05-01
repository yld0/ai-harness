"""3-stage LLM Council orchestration — v3 port.

Stage 1: Collect responses in parallel from all panelist models (best-effort).
Stage 2 (optional): Each panelist anonymously ranks the other responses.
Stage 3: Judge model synthesises consensus, dissent, and final recommendation.

Dependencies are injected so tests can substitute a mock CouncilClient.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any

from ai.council.client import CouncilClient
from ai.council.types import CouncilOpinion, CouncilRanking, CouncilResult

logger = logging.getLogger(__name__)


# ─── Stage 1 ──────────────────────────────────────────────────────────────────


async def _stage1(
    query: str,
    models: list[str],
    client: CouncilClient,
) -> list[CouncilOpinion]:
    responses = await client.query_parallel(models, [{"role": "user", "content": query}])
    opinions: list[CouncilOpinion] = []
    for model in models:
        text = responses.get(model)
        if text is not None:
            opinions.append(CouncilOpinion(model=model, text=text))
        else:
            opinions.append(CouncilOpinion(model=model, text="", failed=True, error="no_response"))
    return opinions


# ─── Stage 2 (optional) ───────────────────────────────────────────────────────

_RANKING_PROMPT = """\
You are evaluating different responses to the following question:

Question: {query}

Here are the responses (anonymised):

{responses_text}

Evaluate each response, then at the end provide a final ranking.

IMPORTANT — format the ranking section EXACTLY as:
FINAL RANKING:
1. Response A
2. Response B
...

Provide your evaluation and ranking now:"""

_CHAIRMAN_PROMPT = """\
You are the Chairman of an LLM Council. Multiple AI models have responded to \
a user's question, and then ranked each other's responses.

Original Question: {query}

STAGE 1 — Individual Responses:
{opinions_text}

STAGE 2 — Peer Rankings:
{rankings_text}

Your task: synthesise a single, comprehensive answer that represents the \
council's collective wisdom. Highlight:
- Points of strong consensus
- Significant dissent or caveats
- Your final recommendation

Provide a clear, well-reasoned final answer:"""


def _parse_ranking(text: str) -> list[str]:
    """Extract ordered 'Response X' labels from a ranking block."""
    if "FINAL RANKING:" in text:
        section = text.split("FINAL RANKING:", 1)[1]
        numbered = re.findall(r"\d+\.\s*(Response [A-Z])", section)
        if numbered:
            return numbered
        return re.findall(r"Response [A-Z]", section)
    return re.findall(r"Response [A-Z]", text)


async def _stage2(
    query: str,
    opinions: list[CouncilOpinion],
    models: list[str],
    client: CouncilClient,
) -> tuple[list[CouncilRanking], dict[str, str]]:
    labels = [chr(65 + i) for i in range(len(opinions))]  # A, B, C, …
    label_to_model = {f"Response {lbl}": op.model for lbl, op in zip(labels, opinions)}
    responses_text = "\n\n".join(f"Response {lbl}:\n{op.text}" for lbl, op in zip(labels, opinions) if not op.failed)
    ranking_prompt = _RANKING_PROMPT.format(query=query, responses_text=responses_text)
    raw_responses = await client.query_parallel(models, [{"role": "user", "content": ranking_prompt}])
    rankings: list[CouncilRanking] = []
    for model in models:
        raw = raw_responses.get(model)
        if raw is not None:
            rankings.append(CouncilRanking(model=model, raw=raw, parsed=_parse_ranking(raw)))
        else:
            rankings.append(CouncilRanking(model=model, raw="", parsed=[], failed=True))
    return rankings, label_to_model


def _aggregate_rankings(rankings: list[CouncilRanking], label_to_model: dict[str, str]) -> list[dict[str, Any]]:
    positions: dict[str, list[int]] = defaultdict(list)
    for r in rankings:
        for pos, label in enumerate(r.parsed, start=1):
            model_name = label_to_model.get(label)
            if model_name:
                positions[model_name].append(pos)
    result: list[dict[str, Any]] = []
    for model, pos_list in positions.items():
        if pos_list:
            result.append(
                {
                    "model": model,
                    "average_rank": round(sum(pos_list) / len(pos_list), 2),
                    "rankings_count": len(pos_list),
                }
            )
    result.sort(key=lambda x: x["average_rank"])
    return result


# ─── Stage 3 ──────────────────────────────────────────────────────────────────


async def _stage3(
    query: str,
    opinions: list[CouncilOpinion],
    rankings: list[CouncilRanking],
    judge_model: str,
    client: CouncilClient,
) -> str:
    opinions_text = "\n\n".join(f"Model: {op.model}\nResponse: {op.text}" for op in opinions if not op.failed)
    rankings_text = "\n\n".join(f"Model: {r.model}\nRanking: {r.raw}" for r in rankings if not r.failed) or "(no peer rankings collected)"
    prompt = _CHAIRMAN_PROMPT.format(query=query, opinions_text=opinions_text, rankings_text=rankings_text)
    result = await client.query(judge_model, [{"role": "user", "content": prompt}])
    if result is None:
        return "Council error: judge model failed to synthesise a response."
    return result


# ─── Public entry point ───────────────────────────────────────────────────────


async def run_council(
    query: str,
    *,
    models: list[str],
    judge_model: str,
    client: CouncilClient | None = None,
    include_rankings: bool = True,
) -> CouncilResult:
    """Run the full 3-stage council and return a ``CouncilResult``.

    *client* is injected for testability; defaults to a live ``CouncilClient``.
    Set *include_rankings* to False to skip Stage 2 and go straight to synthesis.
    One panelist failure never aborts the run.
    """
    if client is None:
        client = CouncilClient()

    # Stage 1 — collect opinions
    logger.info("council stage-1: querying %d models", len(models))
    opinions = await _stage1(query, models, client)
    live_opinions = [op for op in opinions if not op.failed]
    if not live_opinions:
        return CouncilResult(
            final_text="All council panelists failed to respond.",
            opinions=opinions,
            judge_model=judge_model,
        )

    # Stage 2 — optional peer rankings
    rankings: list[CouncilRanking] = []
    label_to_model: dict[str, str] = {}
    aggregate: list[dict[str, Any]] = []
    if include_rankings and len(live_opinions) > 1:
        logger.info("council stage-2: collecting peer rankings")
        rankings, label_to_model = await _stage2(query, live_opinions, models, client)
        aggregate = _aggregate_rankings(rankings, label_to_model)

    # Stage 3 — judge synthesises final answer
    logger.info("council stage-3: synthesising with %s", judge_model)
    final_text = await _stage3(query, live_opinions, rankings, judge_model, client)

    return CouncilResult(
        final_text=final_text,
        opinions=opinions,
        rankings=rankings,
        aggregate_rankings=aggregate,
        judge_model=judge_model,
        metadata={"label_to_model": label_to_model},
    )
