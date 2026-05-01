"""Typed client for the ``ai_*`` GraphQL surface.

Wraps the low-level ``GraphqlClient`` transport with named, typed methods so
callers never construct raw query strings outside this module.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ai.tools.graphql import GraphqlClient

logger = logging.getLogger(__name__)

_CAPTURE_USAGE_MUTATION = """
mutation CaptureUsage($input: UsageCaptureInput!) {
  ai_captureUsage(input: $input)
}
"""


class AIClient:
    """Client for the ``ai_*`` GraphQL namespace."""

    def __init__(self, client: GraphqlClient | None = None) -> None:
        # Lazy import to keep this module importable without tools/ on path.
        if client is None:
            from ai.tools.graphql import GraphqlClient as _GQL

            client = _GQL()
        self._gql = client

    async def capture_usage(
        self,
        *,
        bearer_token: str,
        conversation_id: str,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        thinking_tokens: int = 0,
        cached_tokens: int = 0,
        api_requests: int = 1,
    ) -> bool:
        """Persist LLM token usage for a conversation turn.

        Returns ``True`` if the mutation succeeded, ``False`` on a non-raising
        partial failure (e.g. the mutation returned a falsy value).
        """
        variables: dict[str, Any] = {
            "input": {
                "conversationID": conversation_id,
                "modelID": model_id or "",
                "promptTokens": prompt_tokens,
                "completionTokens": completion_tokens,
                "totalTokens": total_tokens,
                "thinkingTokens": thinking_tokens or 0,
                "cachedTokens": cached_tokens or 0,
                "apiRequests": api_requests,
            }
        }
        logger.debug(
            "ai_captureUsage conversation=%s model=%s tokens=%d",
            conversation_id,
            model_id,
            total_tokens,
        )
        data = await self._gql.execute(
            _CAPTURE_USAGE_MUTATION,
            variables=variables,
            bearer_token=bearer_token,
        )
        return bool(data.get("ai_captureUsage", False))
