"""FastAPI entry point for the AI harness."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware

from ai.agent.runner import AgentRunner
from ai.api import automation_routes, health_routes, routes
from ai.api.main import handle_agent_websocket
from ai.api.ws_connection_manager import WSConnectionManager
from ai.middleware.request_id import RequestIDMiddleware
from ai.config import config, log_config, telemetry_config
from ai.hooks.runner import HookRunner
from ai.telemetry import setup_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_telemetry(telemetry_config)
    app.state.runner = AgentRunner()
    app.state.ws_manager = WSConnectionManager()
    app.state.hook_runner = HookRunner()
    yield


# NOTE: Do not put this into a function, I like the global app variable name
app = FastAPI(
    title="AI Harness",
    root_path="/api/copilot",
    lifespan=lifespan,
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.include_router(health_routes.router)
app.include_router(routes.router)
app.include_router(automation_routes.router)

# Outermost: assigns X-Request-ID + request.state.request_id + ContextVar per HTTP request.
app.add_middleware(RequestIDMiddleware)
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY)


@app.websocket("/v3/ws/{client_id}")
async def ws_route(websocket: WebSocket, client_id: str) -> None:
    await handle_agent_websocket(websocket, client_id, websocket.app.state.runner)


def run() -> None:
    uvicorn.run(
        "ai.main:app",
        host="0.0.0.0",
        port=config.PORT,
        log_level=log_config.LOG_LEVEL.lower(),
        reload=config.RELOAD,
        workers=1,
    )


if __name__ == "__main__":
    run()
