"""Automation-facing v3 routes."""

import time
from collections import OrderedDict
from typing import Any, Annotated

from fastapi import APIRouter, Depends, Header, Request
from pydantic import AliasChoices, Field

from ai.agent.runner import AgentRunner
from ai.api.auth import AuthenticatedUser, get_current_user, optional_bearer_token
from ai.schemas._base import CamelBaseModel
from ai.schemas.agent import AgentChatRequest

IN_MEMORY_TTL_SECONDS = 60 * 60
IN_MEMORY_MAX_ENTRIES = 10_000

router = APIRouter(prefix="/v3/agent", tags=["v3-agent"])


class AutomationRunRequest(AgentChatRequest):
    automation_id: str = Field(
        validation_alias=AliasChoices("automationId", "automationID", "automation_id"),
        serialization_alias="automationId",
    )
    automation_run_id: str = Field(
        validation_alias=AliasChoices("automationRunId", "automationRunID", "automation_run_id"),
        serialization_alias="automationRunId",
    )
    target: str | None = None


class DuplicateAutomationResponse(CamelBaseModel):
    duplicate: bool = True
    original_run_id: str = Field(serialization_alias="originalRunId")


class _ReplayCache:
    def __init__(
        self,
        *,
        ttl_seconds: int = IN_MEMORY_TTL_SECONDS,
        max_entries: int = IN_MEMORY_MAX_ENTRIES,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._values: OrderedDict[tuple[str, str], tuple[float, dict[str, Any]]] = OrderedDict()

    def get(self, key: tuple[str, str]) -> dict[str, Any] | None:
        self._prune()
        item = self._values.get(key)
        if item is None:
            return None
        created_at, value = item
        if time.monotonic() - created_at >= self.ttl_seconds:
            self._values.pop(key, None)
            return None
        self._values.move_to_end(key)
        return value

    def set(self, key: tuple[str, str], value: dict[str, Any]) -> None:
        self._prune()
        self._values[key] = (time.monotonic(), value)
        self._values.move_to_end(key)
        while len(self._values) > self.max_entries:
            self._values.popitem(last=False)

    def clear(self) -> None:
        self._values.clear()

    def _prune(self) -> None:
        now = time.monotonic()
        expired = [key for key, (created_at, _) in self._values.items() if now - created_at >= self.ttl_seconds]
        for key in expired:
            self._values.pop(key, None)


replay_cache = _ReplayCache()


def get_runner(request: Request) -> AgentRunner:
    return request.app.state.runner


@router.post("/run")
async def run_agent(
    body: AutomationRunRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    runner: Annotated[AgentRunner, Depends(get_runner)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    cache_key = (user.user_id, body.automation_run_id)
    cached = replay_cache.get(cache_key)
    if cached is not None:
        return cached

    response = await runner.run(
        body,
        user_id=user.user_id,
        bearer_token=optional_bearer_token(authorization),
    )
    dumped = response.model_dump(by_alias=True, mode="json")
    replay_cache.set(cache_key, dumped)
    return dumped
