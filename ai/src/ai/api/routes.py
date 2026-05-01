"""HTTP routes for the v3 API surface."""

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request

from ai.agent.runner import AgentRunner
from ai.api.auth import AuthenticatedUser, get_current_user, optional_bearer_token
from ai.hooks.base import HookContext, build_hook_context
from ai.hooks.runner import HookRunner
from ai.schemas.agent import AgentChatRequest

router = APIRouter(tags=["v3"])


def get_runner(request: Request) -> AgentRunner:
    return request.app.state.runner


@router.post("/v3/agent/question")
async def ask_agent(
    request: Request,
    body: AgentChatRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    runner: Annotated[AgentRunner, Depends(get_runner)],
    background: BackgroundTasks,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    turn = await runner.run_chat_turn(
        body,
        user_id=user.user_id,
        bearer_token=optional_bearer_token(authorization),
    )
    hook_runner = getattr(request.app.state, "hook_runner", None)
    if hook_runner is not None:
        hctx = build_hook_context(
            user_id=turn.user_id,
            conversation_id=turn.response.conversation_id,
            user_message=turn.user_message,
            response_text=turn.response.response.text,  # type: ignore[union-attr]
            request=turn.request,
            messages=turn.messages,
            turn_index=turn.turn_index,
        )
        background.add_task(_run_post_response_hooks, hook_runner, hctx)
    return turn.response.model_dump(by_alias=True, mode="json")


async def _run_post_response_hooks(hook_runner: HookRunner, hctx: HookContext) -> None:
    await hook_runner.run_after_response(hctx)
