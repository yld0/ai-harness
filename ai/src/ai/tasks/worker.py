"""Arq background worker settings (v3 app does not start a worker; `REDIS_SETTINGS` for ops/parity)."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from arq.connections import RedisSettings

from ai.config import redis_config

logger = logging.getLogger(__name__)

REDIS_SETTINGS = RedisSettings(
    host=redis_config.REDIS_HOST,
    port=redis_config.REDIS_PORT,
    username=(redis_config.REDIS_USERNAME or None) or None,
    password=(redis_config.REDIS_PASSWORD or None) or None,
)


async def startup(ctx: dict[str, Any]) -> None:
    ctx["session"] = httpx.AsyncClient()


async def shutdown(ctx: dict[str, Any]) -> None:
    s = ctx.get("session")
    if s is not None and hasattr(s, "aclose"):
        await s.aclose()


async def recalculate_conversation_title(_ctx: dict[str, Any], user_id: str, conversation_id: str) -> None:
    """Placeholder job — port from v2 when GraphQL wiring is ready."""
    logger.info("recalculate_conversation_title (stub) %s %s", user_id, conversation_id)


class WorkerSettings:  # noqa: D101 — arq CLI entrypoint
    functions = [recalculate_conversation_title]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = REDIS_SETTINGS
