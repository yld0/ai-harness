"""Resolve final URL after following redirects."""

from __future__ import annotations

import logging

import httpx
from aiocache import Cache, cached

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; Yld0Bot/1.0)"


@cached(ttl=60 * 60 * 24, cache=Cache.MEMORY)
async def resolve_final_url(uri: str, timeout: float = 10.0) -> str:
    """Follow redirects; return the final URL or the input uri on failure."""
    if not uri or not uri.startswith(("http://", "https://")):
        return uri
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = await client.get(uri)
            return str(resp.url)
    except Exception as e:
        logger.debug("resolve_final_url failed for %s: %s", uri[:80], e)
        return uri
