"""WebSocket adapter for the v3 chat surface."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional
from dataclasses import dataclass, field

import httpx
from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from ai.agent.runner import AgentTurnResult
from ai.api.auth import (
    AuthenticatedUser,
    decode_token,
    token_from_authorization,
    websocket_auth_error,
)
from ai.api.send import auth_ok_message
from ai.clients.user import UserClient
from ai.config import config
from ai.hooks.types import HookContext
from ai.hooks.runner import HookRunner
from ai.schemas.agent import WsAuthRequest

logger = logging.getLogger(__name__)
HOOK_TASK_DRAIN_GRACE_SECONDS = 5.0


@dataclass
class WebSocketState:
    """Per-connection auth, metadata, and background task state."""

    client_id: str
    user_id: str
    bearer_token: str
    is_superuser: bool = False
    _resolve_task: asyncio.Task[None] | None = None
    hook_tasks: set[asyncio.Task[None]] = field(default_factory=set)


async def receive_json_with_idle_timeout(websocket: WebSocket, client_id: str, timeout: Optional[float] = None) -> object:
    """Receive one JSON frame, enforcing the configured websocket idle timeout.

    Args:
        websocket: The WebSocket connection.
        client_id: The client ID.
        timeout: The timeout in seconds.
    """
    try:
        return await asyncio.wait_for(
            websocket.receive_json(),
            timeout=timeout or config.WS_IDLE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.info("websocket idle timeout (client_id=%s)", client_id)
        await close_websocket(websocket, code=1001, reason="idle timeout")
        raise


class WSConnectionManager:
    """Lifecycle for per-connection ``WebSocketState`` (auth + best-effort metadata)."""

    async def authenticate(self, websocket: WebSocket, client_id: str) -> WebSocketState | None:
        """Authenticate via ``Authorization`` header or retryable first-message auth."""
        header = websocket.headers.get("authorization")
        if header:
            try:
                token = token_from_authorization(header)
                user = decode_token(token)
            except HTTPException as exc:
                message = exc.detail.get("error", {}).get("message", "Invalid bearer token")
                await reject(websocket, message)
                return None
            return self._attach(client_id, user, token)

        failures = 0
        max_failures = max(1, config.WS_MAX_AUTH_FAILURES)
        while failures < max_failures:
            try:
                raw = await receive_json_with_idle_timeout(websocket, client_id)
                auth = WsAuthRequest.model_validate(raw)
                user = decode_token(auth.token)
            except asyncio.TimeoutError:
                logger.info("websocket auth idle timeout (client_id=%s)", client_id)
                await close_websocket(websocket, code=1001, reason="idle timeout")
                return None
            except WebSocketDisconnect:
                raise
            except (json.JSONDecodeError, ValidationError):
                message = "First message must authenticate"
            except HTTPException as exc:
                message = exc.detail.get("error", {}).get("message", "Invalid bearer token")
            else:
                state = self._attach(client_id, user, auth.token)
                await websocket.send_json(auth_ok_message())
                return state

            failures += 1
            await websocket.send_json(websocket_auth_error(message))
            if failures >= max_failures:
                await close_websocket(websocket, code=4401, reason="too many auth failures")
                return None

        return None

    async def disconnect(self, state: WebSocketState) -> None:
        """Drain per-connection background work and cancel best-effort metadata lookup."""
        await drain_hook_tasks(state)

        task = state._resolve_task
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def _attach(self, client_id: str, user: AuthenticatedUser, bearer_token: str) -> WebSocketState:
        """Create a ``WebSocketState`` and kick off the best-effort ``resolve_superuser`` lookup."""
        state = WebSocketState(
            client_id=client_id,
            user_id=user.user_id,
            bearer_token=bearer_token,
        )
        state._resolve_task = asyncio.create_task(resolve_superuser(state))
        return state


async def resolve_superuser(state: WebSocketState) -> None:
    """Best-effort lookup of ``isSuperuser``; transient failures leave the default ``False``."""
    try:
        data = await UserClient().fetch_me(state.bearer_token)
    except (httpx.HTTPStatusError, httpx.RequestError, RuntimeError):
        logger.exception("auth_me lookup failed for client_id=%s", state.client_id)
        return
    state.is_superuser = bool(data.get("isSuperuser"))


async def reject(websocket: WebSocket, message: str, *, code: int = 4401) -> None:
    """Send a ``websocket_auth_error`` frame and close with ``code`` (default 4401)."""
    await websocket.send_json(websocket_auth_error(message))
    await close_websocket(websocket, code=code)


async def close_websocket(websocket: WebSocket, *, code: int = 1000, reason: str | None = None) -> None:
    """
    Close a websocket, ignoring duplicate-close races during cleanup.

    Args:
        websocket: The WebSocket connection.
        code: The close code.
        reason: The close reason.
    """
    try:
        if reason is None:
            await websocket.close(code=code)
        else:
            await websocket.close(code=code, reason=reason)
    except RuntimeError:
        logger.debug("websocket already closed")


async def drain_hook_tasks(state: WebSocketState) -> None:
    """
    Give post-response hook tasks a short graceful drain before cancellation.

    Args:
        state: The WebSocket state.
    """
    tasks = {task for task in state.hook_tasks if not task.done()}
    if not tasks:
        return

    done, pending = await asyncio.wait(tasks, timeout=HOOK_TASK_DRAIN_GRACE_SECONDS)
    if done:
        await asyncio.gather(*done, return_exceptions=True)
    if not pending:
        return

    logger.warning(
        "cancelling %s websocket hook task(s) after %.1fs drain grace (client_id=%s)",
        len(pending),
        HOOK_TASK_DRAIN_GRACE_SECONDS,
        state.client_id,
    )
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
