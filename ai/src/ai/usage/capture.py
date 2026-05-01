"""Usage capture — request cache + async GraphQL persistence.

Request cache
-------------
A module-level LRU cache (max 10 entries) aggregates token metrics keyed by
``request_id`` (set by ``RequestIDMiddleware``).  Use the utility accessors to
inspect recent captures without hitting the database:

    get_request_captures(request_id)   # O(1) lookup for a specific request
    get_latest_captures(n=10)          # most-recent N captures, newest first
    get_capture_by_request_id(rid)     # single-entry dict or None

GraphQL persistence
-------------------
``capture(response)`` is an async function called after every successful LLM
call in ``ProviderRouter.generate()``.  It reads ``bearer_token`` and
``conversation_id`` from ContextVars. When either var is absent (tests, CLI),
the call is a no-op.

Usage in the router::

    await capture(response)  # GQL persistence + cache update (no-op if no ctx)
"""

from __future__ import annotations

import logging
from collections import deque
from typing import TYPE_CHECKING, Any

from ai.context import BEARER_TOKEN, CONVERSATION_ID, REQUEST_ID

if TYPE_CHECKING:
    from ai.providers.base import ProviderResponse

logger = logging.getLogger(__name__)

# ── request cache ─────────────────────────────────────────────────────────────
# Stores aggregated token metrics per request_id (most recent 10 requests).

_request_cache: dict[str, dict[str, Any]] = {}
_request_order: deque[str] = deque(maxlen=10)


def get_capture_by_request_id(request_id: str) -> dict[str, Any] | None:
    """O(1) lookup for a specific request_id. Returns None if not found."""
    return _request_cache.get(request_id)


def get_request_captures(request_id: str | None = None) -> list[dict[str, Any]]:
    """Return cached captures, most recent first.

    If *request_id* is provided returns a one-element list (or empty).
    Otherwise returns all cached entries ordered newest-first.
    """
    if request_id:
        entry = _request_cache.get(request_id)
        return [entry] if entry else []
    return [_request_cache[rid] for rid in reversed(_request_order) if rid in _request_cache]


def get_latest_captures(n: int = 10) -> list[dict[str, Any]]:
    """Return the latest *n* captures, newest first."""
    latest = list(_request_order)[-n:]
    return [_request_cache[rid] for rid in reversed(latest) if rid in _request_cache]


def _cache_usage(request_id: str, usage: dict[str, Any]) -> None:
    """Aggregate *usage* into the per-request cache entry for *request_id*."""
    if request_id in _request_cache:
        entry = _request_cache[request_id]
        for key in ("prompt_tokens", "completion_tokens", "total_tokens", "thinking_tokens", "cached_tokens"):
            entry[key] = entry.get(key, 0) + (usage.get(key) or 0)
    else:
        _request_cache[request_id] = {
            "request_id": request_id,
            "prompt_tokens": usage.get("prompt_tokens") or 0,
            "completion_tokens": usage.get("completion_tokens") or 0,
            "total_tokens": usage.get("total_tokens") or 0,
            "thinking_tokens": usage.get("thinking_tokens") or 0,
            "cached_tokens": usage.get("cached_tokens") or 0,
        }
        _request_order.append(request_id)
        # Evict stale dict entries no longer tracked by the deque.
        current = set(_request_order)
        for stale in [rid for rid in _request_cache if rid not in current]:
            _request_cache.pop(stale, None)


# ── GQL persistence ────────────────────────────────────────────────────────────


def _extract_usage(response: ProviderResponse) -> dict[str, Any] | None:
    """Extract token counts from a normalised ``ProviderResponse``.

    Our providers emit a consistent ``usage`` dict with snake_case keys.
    Returns ``None`` when the response carries no usage data.
    """
    raw = response.usage
    if not raw:
        return None
    prompt = raw.get("prompt_tokens") or 0
    completion = raw.get("completion_tokens") or 0
    total = raw.get("total_tokens") or (prompt + completion)
    if total == 0 and prompt == 0 and completion == 0:
        return None
    return {
        "model_id": response.model or "",
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "thinking_tokens": raw.get("thinking_tokens") or 0,
        "cached_tokens": raw.get("cached_tokens") or 0,
    }


# Module-level singleton — created lazily so tests don't need a live GQL backend.
_client: Any = None


def _ai_client() -> Any:
    global _client
    if _client is None:
        from ai.clients.ai import AIClient

        _client = AIClient()
    return _client


async def capture(
    response: ProviderResponse,
    *,
    started_at: float | None = None,  # accepted but unused; reserved for future latency tracking
) -> None:
    """Persist usage from a completed LLM response to GraphQL.

    Reads ``bearer_token`` and ``conversation_id`` from ContextVars set by
    ``AgentRunner._run_request``.  Silently no-ops when either is absent so
    tests and CLI runs are unaffected.
    """
    bearer_token = BEARER_TOKEN.get()
    conversation_id = CONVERSATION_ID.get()
    request_id = REQUEST_ID.get()

    if not bearer_token or not conversation_id:
        return  # no-op outside a live agent turn

    usage = _extract_usage(response)
    if not usage:
        return

    if request_id:
        _cache_usage(request_id, usage)

    try:
        await _ai_client().capture_usage(
            bearer_token=bearer_token,
            conversation_id=conversation_id,
            model_id=usage["model_id"],
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            thinking_tokens=usage["thinking_tokens"],
            cached_tokens=usage["cached_tokens"],
        )
    except Exception:
        logger.warning("usage capture GQL mutation failed", exc_info=True)
