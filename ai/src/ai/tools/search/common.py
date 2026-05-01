"""Shared HTTP retry and backoff for search / API tool wrappers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import httpx

T = TypeVar("T")

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
BASE_DELAY_S = 0.5


async def with_http_retry(
    call: Callable[[], Awaitable[httpx.Response]],
    *,
    max_attempts: int = MAX_ATTEMPTS,
) -> httpx.Response:
    last: httpx.Response | None = None
    for attempt in range(1, max_attempts + 1):
        response = await call()
        last = response
        if response.status_code in RETRYABLE_STATUS and attempt < max_attempts:
            await asyncio.sleep(BASE_DELAY_S * (2 ** (attempt - 1)))
            continue
        return response
    assert last is not None
    return last


async def json_from_response(response: httpx.Response) -> Any:
    response.raise_for_status()
    return response.json()
