"""WebSocket route handlers for the v3 API."""

import asyncio
import logging
import uuid

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from ai.agent.progress import CollectingProgressSink
from ai.agent.runner import AgentRunner, AgentTurnResult
from ai.api.send import chat_response_event, error_event
from ai.api.ws_connection_manager import (
    WSConnectionManager,
    WebSocketState,
    close_websocket,
    receive_json_with_idle_timeout,
)
from ai.context import REQUEST_ID, bind_context_var
from ai.config import config
from ai.schemas.agent import AgentChatRequest, WsAgentRequest
from ai.hooks.base import HookContext, build_hook_context
from ai.hooks.runner import HookRunner

logger = logging.getLogger(__name__)


def schedule_post_response_hooks(
    state: WebSocketState,
    hook_runner: HookRunner,
    turn: AgentTurnResult,
) -> None:
    """ Schedule post-response hooks for a completed turn on this connection.
    
    Args:
        state: The WebSocket state.
        hook_runner: The HookRunner instance.
        turn: The AgentTurnResult instance.
    """
    hctx = build_hook_context(
        user_id=turn.user_id,
        conversation_id=turn.response.conversation_id,
        user_message=turn.user_message,
        response_text=turn.response.response.text,  # type: ignore[union-attr]
        request=turn.request,
        messages=turn.messages,
        turn_index=turn.turn_index,
    )
    task = asyncio.create_task(run_post_response_hooks(hook_runner, hctx, state.client_id))
    state.hook_tasks.add(task)
    task.add_done_callback(state.hook_tasks.discard)


async def run_post_response_hooks(hook_runner: HookRunner, hctx: HookContext, client_id: str) -> None:
    """ Run post-response hooks without writing late errors to the websocket. """
    try:
        await hook_runner.run_after_response(hctx)
    except Exception:  # noqa: BLE001
        logger.exception("post-response hooks failed for client_id=%s", client_id)


async def handle_chat_turn(
    websocket: WebSocket,
    state: WebSocketState,
    runner: AgentRunner,
    chat_request: AgentChatRequest,
) -> None:
    """
    Run one chat turn and send all progress/final frames for that turn.
    
    Args:
        websocket: The WebSocket connection.
        state: The WebSocket state.
        runner: The AgentRunner instance.
        chat_request: The chat request.
    """
    with bind_context_var(REQUEST_ID, str(uuid.uuid4())):
        progress = CollectingProgressSink()
        try:
            turn = await runner.run_chat_turn(
                chat_request,
                user_id=state.user_id,
                bearer_token=state.bearer_token,
                progress=progress,
            )
        except (asyncio.CancelledError, WebSocketDisconnect):
            logger.info("chat turn cancelled (client_id=%s)", state.client_id)
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error running chat turn")
            wire_message = f"{type(exc).__name__}: {exc}" if state.is_superuser else "Agent run failed."
            await websocket.send_json(
                error_event(
                    code="agent_error",
                    message=wire_message,
                    retryable=True,
                )
            )
            return

        for event in progress.events:
            await websocket.send_json(event)
        await websocket.send_json(chat_response_event(turn.response.model_dump(by_alias=True, mode="json")))

        if hook_runner := getattr(websocket.app.state, "hook_runner", None):
            schedule_post_response_hooks(state, hook_runner, turn)


async def handle_agent_websocket(websocket: WebSocket, client_id: str, runner: AgentRunner) -> None:
    """
    Run authenticated chat turns over a long-lived WebSocket connection.

    Args:
        websocket: The WebSocket connection.
        client_id: The client ID.
        runner: The AgentRunner instance.
    """

    state: WebSocketState | None = None
    await websocket.accept()

    try:
        manager: WSConnectionManager = websocket.app.state.ws_manager
        state = await manager.authenticate(websocket, client_id)
        if state is None:
            return

        while True:
            raw = await receive_json_with_idle_timeout(websocket, client_id, config.WS_IDLE_TIMEOUT_SECONDS)
            request = WsAgentRequest.model_validate(raw)

            await handle_chat_turn(
                websocket,
                state,
                runner,
                request.data,
            )
    except WebSocketDisconnect:
        logger.info("client disconnected (client_id=%s)", client_id)
    finally:
        if state is not None:
            await manager.disconnect(state)
        await close_websocket(websocket)
