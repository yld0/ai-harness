""" Liveness and optional dependency probes. """

from typing import Any

import httpx
from fastapi import APIRouter

from ai.config import health_config

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, Any]:
    """
    Return app health.

    External probes are disabled by default. Set ``HEALTHZ_PROBE_DEPS=true`` to
    attempt lightweight HTTP reachability checks for configured dependency endpoints.
    Failures are reported as error strings, not 500s.
    """
    deps: dict[str, Any] = {
        "graphql": "skipped",
        "gemini": "skipped",
        "openrouter": "skipped",
        "fmp": "skipped",
    }

    if not health_config.HEALTHZ_PROBE_DEPS:
        return {"ok": True, "deps": deps}

    async def _head(client: httpx.AsyncClient, url: str) -> str:
        """ Probe a URL with a HEAD request and return the status code as a string. """
        try:
            r = await client.head(url, follow_redirects=True)
            return f"{r.status_code}"
        except Exception as exc:
            return f"error:{type(exc).__name__}"

    timeout = httpx.Timeout(1.0, connect=0.5)
    async with httpx.AsyncClient(timeout=timeout) as client:
        deps["graphql"] = await _head(client, health_config.GRAPHQL_HEALTH_URL)
        deps["openrouter"] = await _head(client, health_config.OPENROUTER_HEALTH_URL)
        deps["fmp"] = await _head(client, health_config.FMP_HEALTH_URL)
        if health_config.GEMINI_HEALTH_URL:
            deps["gemini"] = await _head(client, health_config.GEMINI_HEALTH_URL)

    return {"ok": True, "deps": deps}
