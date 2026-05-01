"""Shared GraphQL client (Bearer forward, timeouts) for tool use."""

from __future__ import annotations

import os
from typing import Any

import httpx


def _gateway_base() -> str:
    return os.getenv("GATEWAY_URL", "http://localhost:5005")


class GraphqlClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self._base = (base_url or _gateway_base()).rstrip("/")
        self._timeout = timeout_s

    def endpoint(self) -> str:
        return f"{self._base}/graphql"

    async def execute(
        self,
        query: str,
        *,
        variables: dict[str, Any] | None = None,
        bearer_token: str | None = None,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(self.endpoint(), json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()
        if not isinstance(body, dict):
            raise TypeError("GraphQL response must be a JSON object")
        if body.get("errors"):
            raise RuntimeError(str(body["errors"]))
        data = body.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("GraphQL response missing data object")
        return data
