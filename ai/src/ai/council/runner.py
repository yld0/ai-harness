"""Council dispatcher for selecting an implementation version."""

from __future__ import annotations

import logging
from typing import Literal

from ai.config import council_config
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
    """Run the council at the chosen version. Returns a uniform CouncilRunResult."""
    effective_models = models if models is not None else council_config.COUNCIL_MODELS
    effective_judge = judge_model or council_config.CHAIRMAN_MODEL
    logger.info("council dispatch version=%s models=%d", version, len(effective_models))

    if version == "v1":
        from ai.council.v1.adapter import to_council_run_result as v1_adapt
        from ai.council.v1.council import run_council as run_v1

        result = await run_v1(
            query,
            models=effective_models,
            judge_model=effective_judge,
            include_rankings=include_rankings,
        )
        return v1_adapt(result)

    if version == "v2":
        from ai.council.v2.adapter import to_council_run_result as v2_adapt
        from ai.council.v2.council import run_full_council

        no = no_of_council if no_of_council is not None else len(effective_models)
        stage1, stage2, stage3_result, metadata = await run_full_council(query, no_of_council=no)
        return v2_adapt(stage1, stage2, stage3_result, metadata)

    raise ValueError(f"Unknown council version: {version!r}")
