#!/usr/bin/env python3
"""
v3 harness WebSocket smoke client: obtain a JWT, send ``chat_request``, print frames until
``chat_response`` (or an application-level error frame).

**Auth** (first match wins): ``--token``; ``AI_HARNESS_JWT`` / ``GATEWAY_JWT``; ``--mint --sub``
with ``AUTH_SECRETPHRASE`` or ``SECRET_KEY``; or GraphQL ``auth_login`` against
``config.GATEWAY_URL`` using ``--email`` / ``--password``, ``CLIENT_EXAMPLE_EMAIL`` /
``CLIENT_EXAMPLE_PASSWORD``, or an interactive email/password prompt on a TTY.

**Resilience:** transport failures and bad JSON on the wire are logged with a full stack
trace to stderr; the socket is dropped and the current user message is retried after
reconnect (no retyping).

**Env:** importing ``ai.config`` requires ``AUTH_SECRETPHRASE`` and ``SECRET_KEY`` to be
set (same as the rest of the ``ai`` package), even for modes that only use a pasted JWT.

Run from the ``ai/`` directory with dev extras (``websockets``, ``httpx``, ``pyjwt``)::

  uv run --group dev python example/client_ws.py --preset 1
  CLIENT_EXAMPLE_EMAIL=... CLIENT_EXAMPLE_PASSWORD=... uv run --group dev python example/client_ws.py --preset 1
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import logging
import os
import sys
from typing import Any

import httpx
import jwt
import websockets
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import WebSocketException
from websockets.protocol import State

from ai.config import config

logger = logging.getLogger(__name__)

_TRANSPORT_ERRORS = (WebSocketException, OSError)

# (label, query text) — 1-based --preset index
PRESETS: list[tuple[str, str]] = [
    ("hello", "Hello over websocket"),
    ("skills", "/skill list"),
    ("compare", "Compare Apple and Microsoft in one sentence each."),
]

AUTH_LOGIN_MUTATION = """
    mutation AuthLogin($email: String!, $password: String!) {
        auth_login(email: $email, password: $password) {
            accessToken
            tokenType
        }
    }
"""


def jwt_secret() -> str:
    return os.getenv("AUTH_SECRETPHRASE") or os.getenv("SECRET_KEY") or "test-secret"


def _env_jwt() -> str | None:
    for key in ("AI_HARNESS_JWT", "GATEWAY_JWT"):
        v = os.getenv(key, "").strip()
        if v:
            return v
    return None


async def graphql_login(graphql_url: str, email: str, password: str) -> str:
    """Obtain Bearer token via the same ``auth_login`` mutation as ai-master ``example.py``."""
    payload = {
        "query": AUTH_LOGIN_MUTATION,
        "variables": {"email": email, "password": password},
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            graphql_url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError("GraphQL response is not a JSON object")
    if body.get("errors"):
        raise RuntimeError(f"GraphQL errors: {body['errors']}")
    data = body.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("GraphQL response missing data")
    auth = data.get("auth_login")
    if not isinstance(auth, dict):
        raise RuntimeError(f"Unexpected login response: {body!r}")
    token = auth.get("accessToken")
    if not token:
        raise RuntimeError(f"Login response missing accessToken: {body!r}")
    print("Login successful (GraphQL auth_login).", file=sys.stderr)
    return str(token)


def _resolve_email_password(args: argparse.Namespace) -> tuple[str, str] | None:
    email = (args.email or os.getenv("CLIENT_EXAMPLE_EMAIL", "")).strip()
    password = args.password or os.getenv("CLIENT_EXAMPLE_PASSWORD", "")
    if email and not password and sys.stdin.isatty():
        password = getpass.getpass("Password (GraphQL auth_login): ")
    if email and password:
        return email, password
    return None


async def obtain_token(args: argparse.Namespace) -> str:
    if args.token:
        return args.token.strip()
    if args.mint:
        if not args.sub:
            print("--mint requires --sub", file=sys.stderr)
            sys.exit(2)
        return jwt.encode({"sub": args.sub}, jwt_secret(), algorithm="HS256")
    env = _env_jwt()
    if env:
        return env

    creds = _resolve_email_password(args)
    if creds is None and sys.stdin.isatty() and not args.no_prompt:
        print("No JWT in env. GraphQL login (same pattern as ai-master client example).", file=sys.stderr)
        try:
            email = input("Email: ").strip()
        except EOFError:
            email = ""
        if email:
            password = getpass.getpass("Password: ")
            if password:
                creds = (email, password)

    if creds:
        email, password = creds
        url = f"{config.GATEWAY_URL.rstrip('/')}"
        try:
            return await graphql_login(url, email, password)
        except Exception as exc:
            print(f"GraphQL login failed: {exc}", file=sys.stderr)
            sys.exit(2)

    print(
        "No JWT: set CLIENT_EXAMPLE_EMAIL + CLIENT_EXAMPLE_PASSWORD (or use --email/--password), "
        "pass --token, set AI_HARNESS_JWT / GATEWAY_JWT, or use --mint --sub <id>",
        file=sys.stderr,
    )
    sys.exit(2)


def chat_envelope(
    *,
    conversation_id: str,
    query: str,
    route: str,
    mode: str,
) -> dict[str, Any]:
    return {
        "type": "chat_request",
        "data": {
            "conversationID": conversation_id,
            "request": {"query": query},
            "context": {"route": route},
            "mode": mode,
        },
    }


def is_fatal_message(msg: dict[str, Any]) -> bool:
    if "error" in msg:
        return True
    if msg.get("type") == "error":
        return True
    return False


async def run_session(args: argparse.Namespace, token: str) -> int:
    """Drive one or more chat turns. Transport failures log a stack trace, drop the
    socket, and retry the same user message after reconnecting."""
    ws: ClientConnection | None = None
    loop = asyncio.get_event_loop()

    if args.preset is not None:
        _, query = PRESETS[args.preset - 1]
    else:
        query = args.query

    while True:
        if not query:
            try:
                print("================================================")
                query = await loop.run_in_executor(None, lambda: input("\nQuery (or 'exit'): ").strip())
            except EOFError:
                break

        if not query:
            continue
        if query.lower() in ("exit", "quit", "q"):
            break

        if ws is None or ws.state is not State.OPEN:
            print(f"Connecting to {args.url}...", file=sys.stderr)
            extra_headers: list[tuple[str, str]] | None = None
            if not args.auth_first_message:
                extra_headers = [("Authorization", f"Bearer {token}")]
            try:
                ws = await websockets.connect(
                    args.url,
                    additional_headers=extra_headers,
                    open_timeout=30,
                )
                if args.auth_first_message:
                    await ws.send(json.dumps({"type": "authenticate", "token": token}))
                    raw = await ws.recv()
                    try:
                        auth_msg = json.loads(raw)
                    except json.JSONDecodeError:
                        logger.exception("Auth response was not valid JSON; raw=%r", raw[:500])
                        ws = None
                        continue
                    print("Auth response:", json.dumps(auth_msg, indent=2))
                    if auth_msg.get("type") != "auth_ok":
                        print("Authentication failed.", file=sys.stderr)
                        ws = None
                        query = None
                        continue
            except _TRANSPORT_ERRORS:
                logger.exception("WebSocket connect failed; will retry the same message")
                ws = None
                continue

        retry_same_message = False
        try:
            payload = chat_envelope(
                conversation_id=args.conversation_id,
                query=query,
                route=args.route,
                mode=args.mode,
            )
            await ws.send(json.dumps(payload))
            while True:
                raw = await ws.recv()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    logger.exception("Invalid JSON in WebSocket frame; raw=%r", raw[:500])
                    ws = None
                    retry_same_message = True
                    break
                print(json.dumps(msg, indent=2))
                if is_fatal_message(msg):
                    print("Error received, session continuing...", file=sys.stderr)
                    break
                if msg.get("type") == "chat_response":
                    break
        except _TRANSPORT_ERRORS:
            logger.exception("WebSocket error during send/recv; reconnecting, same message will retry")
            ws = None
            continue
        if retry_same_message:
            continue
        # Completed one request/response cycle (or handled fatal app error without transport close)
        query = None

    if ws is not None and ws.state is not State.CLOSED:
        try:
            await ws.close()
        except _TRANSPORT_ERRORS:
            logger.exception("Error while closing WebSocket")

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="v3 harness WebSocket smoke client")
    p.add_argument(
        "--url",
        default="ws://127.0.0.1:8005/v3/ws/ws-example",
        help="WebSocket URL including /v3/ws/{client_id}",
    )
    p.add_argument("--email", default="james.tarball@gmail.com", help="Email for GraphQL auth_login")
    p.add_argument("--password", default=os.getenv("CLIENT_EXAMPLE_PASSWORD"), help="Password for GraphQL auth_login")
    p.add_argument(
        "--no-prompt",
        action="store_true",
        help="Do not prompt for email/password on a TTY when no token is configured",
    )
    p.add_argument("--token", default=None, help="JWT (skips GraphQL login)")
    p.add_argument(
        "--auth-first-message",
        action="store_true",
        help="Send authenticate frame first instead of Authorization header",
    )
    p.add_argument(
        "--mint",
        action="store_true",
        help="Mint HS256 JWT using AUTH_SECRETPHRASE/SECRET_KEY",
    )
    p.add_argument("--sub", default=None, help="JWT sub claim when using --mint")
    p.add_argument("--conversation-id", default="ws-example-conversation", dest="conversation_id")
    p.add_argument("--route", default="chats")
    p.add_argument("--mode", default="auto")
    p.add_argument(
        "--query",
        default="Hello over websocket",
        help="User message (ignored if --preset set)",
    )
    p.add_argument(
        "--preset",
        type=int,
        choices=range(1, len(PRESETS) + 1),
        default=None,
        help=f"Use built-in query (1–{len(PRESETS)}); overrides --query",
    )
    p.add_argument("--list-presets", action="store_true", help="Print presets and exit")
    return p


async def async_main() -> int:
    args = build_parser().parse_args()
    if args.list_presets:
        for i, (name, text) in enumerate(PRESETS, start=1):
            print(f"{i}. {name}: {text}")
        return 0

    if not logging.root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s %(name)s: %(message)s",
            stream=sys.stderr,
        )

    token = await obtain_token(args)
    return await run_session(args, token)


def main() -> None:
    sys.exit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
