"""JWT helpers for the v3 API."""

import os
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Header, HTTPException, Request, WebSocket, status

AUTH_ERROR_CODE = "auth_invalid"


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    claims: dict[str, Any]


def auth_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": AUTH_ERROR_CODE, "message": message}},
    )


def jwt_secret() -> str:
    return os.getenv("AUTH_SECRETPHRASE") or os.getenv("SECRET_KEY") or "test-secret"


def decode_token(token: str) -> AuthenticatedUser:
    try:
        claims = jwt.decode(
            token,
            jwt_secret(),
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise auth_error("Invalid bearer token") from exc

    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        raise auth_error("JWT missing required sub claim")

    return AuthenticatedUser(user_id=sub, claims=claims)


def token_from_authorization(value: str | None) -> str:
    if not value:
        raise auth_error("Missing Authorization bearer token")
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise auth_error("Missing Authorization bearer token")
    return token.strip()


def optional_bearer_token(value: str | None) -> str | None:
    if not value:
        return None
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


async def get_current_user(request: Request, authorization: str | None = Header(default=None)) -> AuthenticatedUser:
    user = decode_token(token_from_authorization(authorization))
    request.state.user_id = user.user_id
    request.state.auth_claims = user.claims
    return user


def websocket_authorization(websocket: WebSocket) -> str | None:
    return websocket.headers.get("authorization")


def websocket_auth_error(message: str) -> dict[str, Any]:
    return {"error": {"code": AUTH_ERROR_CODE, "message": message}}
