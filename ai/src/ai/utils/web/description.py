"""Extract page descriptions for URLs (urlmeta.org, then direct HTML meta)."""

from __future__ import annotations

import hashlib
import logging

import httpx
from aiocache import Cache, cached
from bs4 import BeautifulSoup

from ai.config import urlmeta_config

logger = logging.getLogger(__name__)

URLMETA_BASE = "https://api.urlmeta.org"
DESCRIPTION_CACHE_TTL = 60 * 60 * 24
HEAD_CHUNK_SIZE = 32 * 1024
USER_AGENT = "Mozilla/5.0 (compatible; Yld0Bot/1.0)"


async def _fetch_urlmeta(url: str) -> str:
    api_key = getattr(urlmeta_config, "URLMETA_API_KEY", None) or ""
    if not api_key:
        return ""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{URLMETA_BASE}/meta",
                params={"url": url},
                headers={
                    "Authorization": f"Basic {api_key}",
                    "User-Agent": USER_AGENT,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            meta = data.get("meta") or {}
            return (meta.get("description") or "").strip()
    except Exception as e:
        logger.debug("urlmeta fetch failed for %s: %s", url[:80], e)
        return ""


async def _fetch_meta_direct(url: str) -> str:
    try:
        async with httpx.AsyncClient(
            timeout=8.0,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.content[:HEAD_CHUNK_SIZE]
            soup = BeautifulSoup(content, "html.parser")
            og = soup.find("meta", attrs={"property": "og:description"})
            if og and og.get("content"):
                return (og["content"] or "").strip()
            meta = soup.find("meta", attrs={"name": "description"})
            if meta and meta.get("content"):
                return (meta["content"] or "").strip()
    except Exception as e:
        logger.debug("direct meta fetch failed for %s: %s", url[:80], e)
    return ""


def _desc_cache_key(_f: object, *args: object, **kwargs: object) -> str:
    url = str(args[0]) if args else ""
    return f"url_desc:{hashlib.md5(url.encode()).hexdigest()}"


@cached(ttl=DESCRIPTION_CACHE_TTL, cache=Cache.MEMORY, key_builder=_desc_cache_key)
async def get_description(url: str) -> str:
    if not url or not url.startswith(("http://", "https://")):
        return ""
    desc = await _fetch_urlmeta(url)
    if desc:
        return desc
    return await _fetch_meta_direct(url)
