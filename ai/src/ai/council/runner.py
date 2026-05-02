"""Council dispatcher for selecting an implementation version."""

from __future__ import annotations

import logging
from typing import Literal

from ai.config import council_config
from ai.council.v1.council import V1Council
from ai.council.v2.council import V2Council
from ai.schemas.agent import CouncilRunResult

logger = logging.getLogger(__name__)

CouncilVersion = Literal["v1", "v2"]
DEFAULT_VERSION: CouncilVersion = "v2"


async def run_council(
    query: str,
    *,
    version: CouncilVersion = DEFAULT_VERSION,
    models: list[str] | None = None,
    judge_model: str | None = None,
    include_rankings: bool = True,
    no_of_council: int | None = None,
) -> CouncilRunResult:
    """
    Run the council at the chosen version. Returns a uniform ``CouncilRunResult``.

    Args:
        query: The user's question
        version: The council version to use
        models: The list of models to use
        judge_model: The judge model to use
        include_rankings: Whether to include rankings
        no_of_council: The number of council members to use

    Returns:
        A uniform ``CouncilRunResult``.
    """

    effective_models = models if models is not None else council_config.COUNCIL_MODELS
    effective_judge = judge_model or council_config.CHAIRMAN_MODEL
    logger.info(f"[run_council][runner] council dispatch version={version} models={len(effective_models)}")

    match version:
        case "v1":
            return await V1Council().run(
                query,
                models=effective_models,
                judge_model=effective_judge,
                include_rankings=include_rankings,
                no_of_council=no_of_council,
            )
        case "v2":
            return await V2Council().run(
                query,
                models=effective_models,
                judge_model=effective_judge,
                include_rankings=include_rankings,
                no_of_council=no_of_council,
            )
        case _:
            raise ValueError(f"Unknown council version: {version!r}")
