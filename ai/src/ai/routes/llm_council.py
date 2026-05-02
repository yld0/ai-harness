"""Route handler: llm-council.

Runs the 3-stage LLM Council (Phase 15):
  Stage 1 — parallel panelist responses
  Stage 2 — optional peer ranking
  Stage 3 — judge synthesis

Input keys (all optional):
  ``query``              — the question to put to the council (defaults to the
                           request's user query text).
  ``models``             — list[str] override for panelist model IDs.
  ``judge_model``        — str override for the synthesising judge.
  ``include_rankings``   — bool, default True.
  ``council_version``    — "v1" or "v2"; defaults to route metadata or v2.
"""

from __future__ import annotations

import logging

from ai.config import council_config
from ai.council.runner import DEFAULT_VERSION, CouncilVersion, run_council
from ai.routes.context import RouteContext, RouteResult

logger = logging.getLogger(__name__)


def _str_to_models(s: str) -> list[str]:
    return [m.strip() for m in s.split(",") if m.strip()]


def _route_metadata(ctx: RouteContext) -> dict:
    request = ctx.request
    context = getattr(request, "context", None)
    route_metadata = getattr(context, "route_metadata", None)
    return route_metadata or {}


async def run(ctx: RouteContext) -> RouteResult:
    route_metadata = _route_metadata(ctx)

    # Resolve the query
    query: str = ctx.input.get("query", "")
    if not query:
        # Fall back to the request's user query text
        req = ctx.request
        if req is not None:
            query = getattr(getattr(req, "request", None), "query", "") or ""
    if not query:
        return RouteResult(text="No query provided for council.", ok=False, error="missing_input")

    # Resolve models
    models_input = ctx.input.get("models")
    if isinstance(models_input, list):
        models = [str(m) for m in models_input if m]
    elif isinstance(models_input, str) and models_input:
        models = _str_to_models(models_input)
    else:
        models = list(council_config.COUNCIL_MODELS)

    if not models:
        return RouteResult(text="No council models configured.", ok=False, error="no_models")

    judge_model: str = ctx.input.get("judge_model") or council_config.CHAIRMAN_MODEL

    include_rankings_raw = ctx.input.get("include_rankings")
    include_rankings = True if include_rankings_raw is None else bool(include_rankings_raw)
    version: CouncilVersion = ctx.input.get("council_version") or route_metadata.get("council_version") or DEFAULT_VERSION
    no_of_council = ctx.input.get("no_of_council") or route_metadata.get("no_of_council")

    await ctx.progress.emit(
        "task_progress",
        {
            "task_id": "llm-council",
            "title": f"Council: querying {len(models)} panelists",
            "items": [{"type": "item", "content": f"Models: {', '.join(models)}"}],
            "default_open": True,
        },
    )

    try:
        result = await run_council(
            query,
            version=version,
            models=models,
            judge_model=judge_model,
            include_rankings=include_rankings,
            no_of_council=int(no_of_council) if no_of_council is not None else None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("llm-council: run_council raised")
        return RouteResult(text=f"Council failed: {exc}", ok=False, error="council_error")

    judge = result.stage3.model if result.stage3 is not None else judge_model
    final_text = result.stage3.response if result.stage3 is not None else "Council failed to synthesise a response."

    await ctx.progress.emit(
        "task_progress",
        {
            "task_id": "llm-council",
            "title": "Council complete",
            "items": [
                {"type": "item", "content": f"Version: {result.version}"},
                {"type": "item", "content": f"Judge: {judge}"},
                {"type": "item", "content": f"Panelists: {len(models)}"},
            ],
        },
    )

    # Build structured metadata for the caller
    sub_opinions = [
        {
            "model": item.model,
            "text": item.response[:2000],  # truncate for metadata size
            "failed": False,
        }
        for item in result.stage1
    ]
    metadata = {
        "route": "llm-council",
        "council_version": result.version,
        "judge_model": judge,
        "panelists": len(models),
        "panelists_succeeded": len(result.stage1),
        "opinions": sub_opinions,
        "rankings": [ranking.model_dump() for ranking in result.stage2],
        "aggregate_rankings": [ranking.model_dump() for ranking in result.aggregate_rankings],
        **result.metadata,
    }
    return RouteResult(text=final_text, metadata=metadata)
