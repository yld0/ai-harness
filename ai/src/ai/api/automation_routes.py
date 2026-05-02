""" Automation-facing v3 routes. """

from typing import Annotated, Any

import aiocache
from fastapi import APIRouter, Depends, Header, Request
from pydantic import AliasChoices, Field

from ai.agent.runner import AgentRunner
from ai.api.auth import AuthenticatedUser, get_current_user, optional_bearer_token
from ai.config import automation_config
from ai.schemas._base import CamelBaseModel
from ai.schemas.agent import AgentChatRequest

router = APIRouter(prefix="/v3/agent", tags=["v3-agent"])

replay_cache: aiocache.SimpleMemoryCache = aiocache.SimpleMemoryCache()


class AutomationRunRequest(AgentChatRequest):
    """ Automation-specific request envelope carrying idempotency IDs.
    
    Args:
        automation_id: The automation ID.
        automation_run_id: The automation run ID.
        target: The target.
    """
    automation_id: str = Field(
        validation_alias=AliasChoices("automationId", "automationID", "automation_id"),
        serialization_alias="automationId",
    )
    automation_run_id: str = Field(
        validation_alias=AliasChoices("automationRunId", "automationRunID", "automation_run_id"),
        serialization_alias="automationRunId",
    )
    target: str | None = None


def get_runner(request: Request) -> AgentRunner:
    """ Return the shared ``AgentRunner`` from application state. """
    return request.app.state.runner


@router.post("/run")
async def run_agent(
    body: AutomationRunRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    runner: Annotated[AgentRunner, Depends(get_runner)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """ Execute one automation turn, replaying the cached result for duplicate run IDs.
    
    Args:
        body: The automation run request.
        user: The authenticated user.
        runner: The AgentRunner instance.
        authorization: The authorization header.
    """

    cache_key = f"{user.user_id}:{body.automation_run_id}"
    cached: dict[str, Any] | None = await replay_cache.get(cache_key)
    if cached is not None:
        return cached

    response = await runner.run(
        body,
        user_id=user.user_id,
        bearer_token=optional_bearer_token(authorization),
    )
    dumped = response.model_dump(by_alias=True, mode="json")
    await replay_cache.set(cache_key, dumped, ttl=automation_config.AUTOMATION_REPLAY_TTL_SECONDS)
    return dumped
