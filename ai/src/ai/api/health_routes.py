"""Liveness and dependency probes."""

import os
from typing import Any

import httpx
from fastapi import APIRouter

router = APIRouter(tags=["health"])


def _env_flag(name: str) -> bool:
    return os.getenv(name, "0") in ("1", "true", "True", "yes", "Y")


@router.get("/healthz")
async def healthz() -> dict[str, Any]:
    """Return app health. External probes are optional and disabled in tests by default.

    Set ``HEALTHZ_PROBE_DEPS=1`` to attempt lightweight HTTP reachability checks for
    configured endpoints (best-effort; failures are reported as error strings, not 500s).
    """
    deps: dict[str, Any] = {
        "graphql": "skipped",
        "gemini": "skipped",
        "openrouter": "skipped",
        "fmp": "skipped",
    }

    if not _env_flag("HEALTHZ_PROBE_DEPS"):
        return {"ok": True, "deps": deps}

    timeout = httpx.Timeout(1.0, connect=0.5)
    client = httpx.AsyncClient(timeout=timeout)

    async def _head(url: str) -> str:
        try:
            r = await client.head(url, follow_redirects=True)
            return f"{r.status_code}"
        except Exception as exc:
            return f"error:{type(exc).__name__}"

    try:
        # Best-effort defaults; real URLs come later from config / env.
        graphql_url = os.getenv("GRAPHQL_HEALTH_URL", "http://127.0.0.1:5005/healthz")
        gemini_url = os.getenv("GEMINI_HEALTH_URL", "")
        openrouter_url = os.getenv("OPENROUTER_HEALTH_URL", "https://openrouter.ai/healthz")
        fmp_url = os.getenv("FMP_HEALTH_URL", "https://financialmodelingprep.com")

        deps["graphql"] = await _head(graphql_url)
        deps["openrouter"] = await _head(openrouter_url)
        deps["fmp"] = await _head(fmp_url)
        if gemini_url:
            deps["gemini"] = await _head(gemini_url)
    finally:
        await client.aclose()

    return {"ok": True, "deps": deps}
