"""Per-user TTL cache for rules snapshots.

Rules are fetched once per session and reused across turns until the TTL
expires.  A short TTL (default 5 min) keeps the cache warm within a session
while allowing rule changes to propagate.

Key design choices:
- Cache key: ``user_id + truncated SHA-256 of bearer_token`` so token rotation
  automatically produces a cache miss.
- Missing/None bearer_token → empty snapshot (no rules, no crash).
- Network errors in ``fetch_rules_snapshot`` → empty snapshot (fail-safe).
- ``invalidate(user_id, bearer_token)`` supports manual invalidation (e.g. after
  a rule is added via the rules mutation tools in Phase 13+).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Any

from ai.clients.rules import fetch_rules_snapshot
from ai.rules.models import RulesSnapshot

logger = logging.getLogger(__name__)

DEFAULT_TTL = 300  # 5 minutes


def _cache_key(user_id: str, bearer_token: str) -> str:
    token_hash = hashlib.sha256(bearer_token.encode()).hexdigest()[:16]
    return f"{user_id}:{token_hash}"


class RulesCache:
    """
    Process-local per-user rules cache with configurable TTL.

    Args:
        ttl_s: Seconds before a cached snapshot is considered stale.
               Defaults to ``DEFAULT_TTL`` (300 s).
    """

    def __init__(self, ttl_s: float | None = None) -> None:
        self._ttl = ttl_s if ttl_s is not None else DEFAULT_TTL
        # key → (monotonic timestamp of fetch, snapshot)
        self._store: dict[str, tuple[float, RulesSnapshot]] = {}
        self._lock = asyncio.Lock()

    async def load(
        self,
        user_id: str,
        bearer_token: str | None,
        *,
        client: Any | None = None,
    ) -> RulesSnapshot:
        """Return a cached snapshot or fetch a fresh one.

        Args:
            user_id:      Caller's user identifier.
            bearer_token: JWT forwarded from the HTTP request.
                          ``None`` → empty snapshot (unauthenticated callers).
            client:       Optional ``GraphqlClient`` override (for tests).
        """
        if not bearer_token:
            return RulesSnapshot()

        key = _cache_key(user_id, bearer_token)

        # Fast path: check cache without holding the lock for the fetch
        async with self._lock:
            entry = self._store.get(key)
            if entry is not None:
                stored_at, snapshot = entry
                if time.monotonic() - stored_at < self._ttl:
                    return snapshot

        # Slow path: fetch from GraphQL
        try:
            snapshot = await fetch_rules_snapshot(bearer_token, client=client)
        except Exception as exc:  # noqa: BLE001
            logger.warning("rules fetch failed for user %s: %s", user_id, exc)
            snapshot = RulesSnapshot()

        async with self._lock:
            self._store[key] = (time.monotonic(), snapshot)

        return snapshot

    def invalidate(self, user_id: str, bearer_token: str) -> None:
        """Remove a cached entry so the next call fetches fresh data."""
        key = _cache_key(user_id, bearer_token)
        self._store.pop(key, None)

    def clear(self) -> None:
        """Flush the entire in-process cache (useful in tests)."""
        self._store.clear()
