"""Shared HTTP forwarder: gateway → harness ``POST /v3/agent/question``.

All gateway adapters (WhatsApp, Discord, …) funnel inbound messages through
this module.  It constructs a minimal ``AgentChatRequestV3``-compatible JSON
body, posts it to the running harness, and returns the response text.

Configuration (environment variables):
    HARNESS_URL   — Base URL of the harness service (default http://localhost:8005).
    GATEWAY_JWT   — Bearer token to attach to forwarded requests.  Gateways
                    may override per-call with their own user token.
    GATEWAY_TIMEOUT_S — Per-request HTTP timeout in seconds (default 60).
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_HARNESS_URL = "http://localhost:8005"
_DEFAULT_TIMEOUT = 60.0
_V3_QUESTION_PATH = "/v3/agent/question"


# ─── Rate limiter ─────────────────────────────────────────────────────────────


class RateLimiter:
    """Simple sliding-window in-process rate limiter keyed by sender id.

    Not suitable for multi-process deployments — use Redis/token-bucket there.
    """

    def __init__(self, max_requests: int = 10, window_seconds: float = 60.0) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._log: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, sender_id: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window
        hits = [t for t in self._log[sender_id] if t >= cutoff]
        self._log[sender_id] = hits
        if len(hits) >= self._max:
            logger.warning("rate limit exceeded for sender %r", sender_id)
            return False
        self._log[sender_id].append(now)
        return True

    def reset(self, sender_id: str | None = None) -> None:
        """Clear limits — useful in tests."""
        if sender_id is None:
            self._log.clear()
        else:
            self._log.pop(sender_id, None)


# Global rate limiter; gateways may replace with a custom instance.
default_rate_limiter = RateLimiter(
    max_requests=int(os.getenv("GATEWAY_RATE_LIMIT_MAX", "10")),
    window_seconds=float(os.getenv("GATEWAY_RATE_LIMIT_WINDOW_S", "60")),
)


# ─── Request builder ──────────────────────────────────────────────────────────


def build_request_body(
    text: str,
    *,
    user_id: str,
    conversation_id: str,
    channel: str = "whatsapp",
    mode: str = "auto",
    model: Optional[str] = None,
) -> dict[str, Any]:
    """Return a JSON-serialisable dict matching ``AgentChatRequestV3``."""
    request: dict[str, Any] = {"query": text}
    if model:
        request["model"] = model
    return {
        "conversationId": conversation_id,
        "request": request,
        "context": {
            "routeMetadata": {"channel": channel},
        },
        "mode": mode,
    }


# ─── Forwarder ────────────────────────────────────────────────────────────────


class HarnessForwarder:
    """Forwards a gateway message to the harness and returns the response text.

    Parameters
    ----------
    harness_url:
        Base URL of the running harness (env: ``HARNESS_URL``).
    bearer_token:
        JWT to attach as ``Authorization: Bearer <token>``
        (env: ``GATEWAY_JWT``).
    timeout:
        HTTP timeout in seconds (env: ``GATEWAY_TIMEOUT_S``).
    rate_limiter:
        Optional rate limiter; pass ``None`` to skip rate limiting.
    """

    def __init__(
        self,
        harness_url: str | None = None,
        bearer_token: str | None = None,
        timeout: float | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.harness_url = (harness_url or os.getenv("HARNESS_URL") or _DEFAULT_HARNESS_URL).rstrip("/")
        self.bearer_token = bearer_token or os.getenv("GATEWAY_JWT") or ""
        self.timeout = timeout if timeout is not None else float(os.getenv("GATEWAY_TIMEOUT_S", str(_DEFAULT_TIMEOUT)))
        self.rate_limiter = rate_limiter if rate_limiter is not None else default_rate_limiter

    async def forward(
        self,
        text: str,
        *,
        user_id: str,
        conversation_id: str,
        channel: str = "whatsapp",
        mode: str = "auto",
        bearer_token: Optional[str] = None,
    ) -> str:
        """Forward *text* to the harness; return the response text.

        Raises ``httpx.HTTPError`` on HTTP-level failures.
        Raises ``RateLimitError`` when the sender is throttled.
        """
        if self.rate_limiter is not None and not self.rate_limiter.is_allowed(user_id):
            raise RateLimitError(f"Rate limit exceeded for {user_id!r}")

        body = build_request_body(
            text,
            user_id=user_id,
            conversation_id=conversation_id,
            channel=channel,
            mode=mode,
        )
        token = bearer_token or self.bearer_token
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        url = self.harness_url + _V3_QUESTION_PATH
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()

        data = resp.json()
        # AgentChatResponseV3: { response: { text: "..." } }
        return (data.get("response") or {}).get("text") or ""


class RateLimitError(Exception):
    """Raised when the per-sender rate limit is exceeded."""
