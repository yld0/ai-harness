"""HTTP-scoped and agent-scoped ContextVars.

``REQUEST_ID``      — set by ``RequestIDMiddleware`` for every HTTP/WS request.
``BEARER_TOKEN``    — set by ``AgentRunner._run_request`` for the duration of a turn.
``CONVERSATION_ID`` — set by ``AgentRunner._run_request`` for the duration of a turn.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TypeVar

T = TypeVar("T")

REQUEST_ID: ContextVar[str | None] = ContextVar("request_id", default=None)
BEARER_TOKEN: ContextVar[str | None] = ContextVar("bearer_token", default=None)
CONVERSATION_ID: ContextVar[str | None] = ContextVar("conversation_id", default=None)


@contextmanager
def bind_context_var(context_var: ContextVar[T], value: T) -> Iterator[None]:
    """Bind a ContextVar for the duration of a ``with`` block."""
    token = context_var.set(value)
    try:
        yield
    finally:
        context_var.reset(token)
