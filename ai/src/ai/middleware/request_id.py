"""Propagate ``X-Request-ID`` (generate if absent) and expose on ``request.state``."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ai.context import REQUEST_ID


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Set ``request.state.request_id``, mirror on response, bind ContextVar for the request."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:

        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        token = REQUEST_ID.set(request_id)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            REQUEST_ID.reset(token)
