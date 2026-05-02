"""Low-level GraphQL transport shared by namespace clients."""

from __future__ import annotations

from typing import Any

import httpx

from ai.config import config


class GraphqlError(RuntimeError):
    """GraphQL response containing one or more errors."""

    def __init__(self, message: str, errors: list[dict[str, Any]]) -> None:
        """Store the response message and raw GraphQL error payload."""
        super().__init__(message)
        self.errors = errors


class GraphqlClient:
    """Thin HTTP adapter for the gateway GraphQL endpoint."""

    def __init__(self, gateway_url: str | None = None) -> None:
        """Initialize the transport with an optional gateway URL override."""
        self.gateway_url = gateway_url or config.GATEWAY_URL

    async def execute(
        self,
        query: str,
        *,
        variables: dict[str, Any] | None = None,
        bearer_token: str | None = None,
    ) -> dict[str, Any]:
        """Execute a GraphQL operation and return the response ``data`` object."""
        headers = {"Content-Type": "application/json"}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.gateway_url,
                json={"query": query, "variables": variables or {}},
                headers=headers,
            )
            response.raise_for_status()

        payload = response.json()
        errors = payload.get("errors") or []
        if errors:
            message = "; ".join(str(error.get("message", error)) for error in errors)
            raise GraphqlError(message, errors)

        data = payload.get("data")
        return data if isinstance(data, dict) else {}
