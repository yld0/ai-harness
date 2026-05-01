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
  ``include_rankings``   — bool, default from COUNCIL_INCLUDE_RANKINGS env.
  ``timeout``            — float, per-model HTTP timeout seconds.
"""

from __future__ import annotations

import logging
import os

from ai.council.client import CouncilClient
from ai.council.council import run_council
from ai.routes.context import RouteContext, RouteResult

logger = logging.getLogger(__name__)

_DEFAULT_MODELS_STR = os.getenv(
    "COUNCIL_MODELS",
    "openai/gpt-4o,anthropic/claude-sonnet-4-5,google/gemini-2.0-flash-001",
)
_DEFAULT_CHAIRMAN = os.getenv("COUNCIL_CHAIRMAN_MODEL", "anthropic/claude-sonnet-4-5")


def _str_to_models(s: str) -> list[str]:
    return [m.strip() for m in s.split(",") if m.strip()]


async def run(ctx: RouteContext) -> RouteResult:
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
        models = _str_to_models(_DEFAULT_MODELS_STR)

    if not models:
        return RouteResult(text="No council models configured.", ok=False, error="no_models")

    judge_model: str = ctx.input.get("judge_model") or _DEFAULT_CHAIRMAN

    include_rankings_raw = ctx.input.get("include_rankings")
    if include_rankings_raw is None:
        include_rankings = os.getenv("COUNCIL_INCLUDE_RANKINGS", "1").lower() in (
            "1",
            "true",
            "yes",
        )
    else:
        include_rankings = bool(include_rankings_raw)

    timeout: float = float(ctx.input.get("timeout", os.getenv("COUNCIL_TIMEOUT_S", "120")))

    await ctx.progress.emit(
        "task_progress",
        {
            "task_id": "llm-council",
            "title": f"Council: querying {len(models)} panelists",
            "items": [{"type": "item", "content": f"Models: {', '.join(models)}"}],
            "default_open": True,
        },
    )

    client = CouncilClient(timeout=timeout)
    try:
        result = await run_council(
            query,
            models=models,
            judge_model=judge_model,
            client=client,
            include_rankings=include_rankings,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("llm-council: run_council raised")
        return RouteResult(text=f"Council failed: {exc}", ok=False, error="council_error")

    await ctx.progress.emit(
        "task_progress",
        {
            "task_id": "llm-council",
            "title": "Council complete",
            "items": [
                {"type": "item", "content": f"Judge: {result.judge_model}"},
                {"type": "item", "content": f"Panelists: {len(result.opinions)}"},
            ],
        },
    )

    # Build structured metadata for the caller
    sub_opinions = [
        {
            "model": op.model,
            "text": op.text[:2000],  # truncate for metadata size
            "failed": op.failed,
            **({"error": op.error} if op.error else {}),
        }
        for op in result.opinions
    ]
    metadata = {
        "route": "llm-council",
        "judge_model": result.judge_model,
        "panelists": len(result.opinions),
        "panelists_succeeded": sum(1 for op in result.opinions if not op.failed),
        "opinions": sub_opinions,
        "aggregate_rankings": result.aggregate_rankings,
        **result.metadata,
    }
    return RouteResult(text=result.final_text, metadata=metadata)
