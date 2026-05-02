"""Async HTTP client for OpenRouter-based council model calls.

Injects no v2 dependencies.  Each call returns an Optional str — None means
the model failed (best-effort semantics: one failure never aborts the run).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Sequence

import httpx

from ai.config import council_config

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 120.0


class CouncilClient:
    """Thin async wrapper around the OpenRouter chat completions endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self.api_key = api_key or council_config.OPENROUTER_API_KEY
        self.api_url = api_url or council_config.OPENROUTER_API_URL
        self.timeout = timeout

    async def query(
        self,
        model: str,
        messages: list[dict[str, str]],
    ) -> Optional[str]:
        """Call *model* with *messages*; return assistant text or None on error."""
        if not self.api_key:
            logger.warning("council: OPENROUTER_API_KEY not set — model %s skipped", model)
            return None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": model, "messages": messages}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                resp = await http.post(self.api_url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"].get("content") or ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("council: model %s failed: %s", model, exc)
            return None

    async def query_parallel(self, models: Sequence[str], messages: list[dict[str, str]]) -> dict[str, Optional[str]]:
        """Query all *models* concurrently; return {model: text_or_None}."""
        results = await asyncio.gather(
            *[self.query(m, messages) for m in models],
            return_exceptions=False,
        )
        return {model: text for model, text in zip(models, results)}
