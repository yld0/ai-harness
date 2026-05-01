"""WebSocket route handlers for the v3 API."""

import asyncio
import logging
import uuid

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from ai.agent.progress import CollectingProgressSink
from ai.agent.runner import AgentRunner
from ai.api.send import chat_response_event, error_event
from ai.api.ws_connection_manager import (
    WSConnectionManager,
    WebSocketState,
    close_websocket,
    receive_json_with_idle_timeout,
    schedule_post_response_hooks,
)
from ai.context import REQUEST_ID, bind_context_var
from ai.schemas.agent import AgentChatRequest, WsAgentRequest, WsClientMessageType

logger = logging.getLogger(__name__)


async def handle_chat_turn(
    websocket: WebSocket,
    state: WebSocketState,
    runner: AgentRunner,
    chat_request: AgentChatRequest,
    hook_runner,
) -> None:
    """Run one chat turn and send all progress/final frames for that turn."""
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
        if hook_runner is not None:
            schedule_post_response_hooks(state, hook_runner, turn)


async def websocket_endpoint(websocket: WebSocket, client_id: str, runner: AgentRunner) -> None:
    """Run authenticated v3 chat turns over a long-lived WebSocket connection."""

    state: WebSocketState | None = None
    await websocket.accept()

    try:
        manager: WSConnectionManager = websocket.app.state.ws_manager
        state = await manager.authenticate(websocket, client_id)
        if state is None:
            return

        while True:
            try:
                raw = await receive_json_with_idle_timeout(websocket)
            except asyncio.TimeoutError:
                logger.info("websocket idle timeout (client_id=%s)", client_id)
                await close_websocket(websocket, code=1001, reason="idle timeout")
                break

            try:
                request = WsAgentRequest.model_validate(raw)
            except ValidationError:
                await websocket.send_json(
                    error_event(
                        code="bad_envelope",
                        message="Invalid request envelope.",
                        retryable=False,
                    )
                )
                continue

            if request.type != WsClientMessageType.CHAT_REQUEST or not isinstance(request.data, AgentChatRequest):
                await websocket.send_json(
                    error_event(
                        code="unsupported_message_type",
                        message="Unsupported websocket message type.",
                        retryable=False,
                    )
                )
                continue

            await handle_chat_turn(
                websocket,
                state,
                runner,
                request.data,
                getattr(websocket.app.state, "hook_runner", None),
            )
    except WebSocketDisconnect:
        logger.info("client disconnected (client_id=%s)", client_id)
    finally:
        if state is not None:
            await manager.disconnect(state)
            await close_websocket(websocket)
