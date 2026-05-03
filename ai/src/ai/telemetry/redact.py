"""Shared redaction for Sentry, PostHog, and Langfuse captures."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from typing import Literal, TypedDict

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_AUTH_LINE_RE = re.compile(r"(?i)\bauthorization\s*:\s*(bearer\s+)?[^\s\r\n]+")

_EXACT_SENSITIVE_KEYS = frozenset(
    (
        "authorization",
        "password",
        "secret",
        "bearer",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "id_token",
        "client_secret",
    )
)


class _RedactedLargeString(TypedDict):
    _redacted: Literal[True]
    len: int
    sha256_16: str


@dataclass(frozen=True)
class RedactSettings:
    redact_prompts: bool
    redact_tool_args: bool


def scrub_secrets_str(value: str) -> str:
    """Remove emails and Authorization patterns (always, regardless of redact flags)."""
    s = _EMAIL_RE.sub("[email_redacted]", value)
    s = _AUTH_LINE_RE.sub("Authorization: [redacted]", s)
    return s


def _is_sensitive_key(key: str) -> bool:
    lower = key.lower().replace("-", "_")
    return lower in _EXACT_SENSITIVE_KEYS or lower.endswith("_secret") or lower.endswith("_password") or lower.endswith("_token")


def _redact_scalar_str(s: str, *, content_redact: bool) -> str | _RedactedLargeString:
    cleaned = scrub_secrets_str(s)
    if not content_redact or len(cleaned) < 32:
        return cleaned
    digest = hashlib.sha256(cleaned.encode("utf-8", errors="replace")).hexdigest()
    return {
        "_redacted": True,
        "len": len(cleaned),
        "sha256_16": digest[:16],
    }


def redact_value(value: object, settings: RedactSettings, *, mode: str) -> object:
    """Redact a JSON-like structure.

    ``mode``:
      - ``prompt`` — apply ``TELEMETRY_REDACT_PROMPTS`` to string payloads.
      - ``tool_args`` — apply ``TELEMETRY_REDACT_TOOL_ARGS`` to string payloads.
      - ``general`` — follow prompt flag for unstructured analytics payloads.
    """
    if mode == "prompt":
        content_redact = settings.redact_prompts
    elif mode == "tool_args":
        content_redact = settings.redact_tool_args
    else:
        content_redact = settings.redact_prompts

    return _walk(value, content_redact=content_redact)


def _walk(value: object, *, content_redact: bool) -> object:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value
    if isinstance(value, str):
        return _redact_scalar_str(value, content_redact=content_redact)
    if isinstance(value, dict):
        out: dict[object, object] = {}
        for k, v in value.items():
            sk = str(k)
            if _is_sensitive_key(sk):
                out[k] = "[redacted]"
                continue
            out[k] = _walk(v, content_redact=content_redact)
        return out
    if isinstance(value, list):
        return [_walk(item, content_redact=content_redact) for item in value]
    if isinstance(value, tuple):
        return tuple(_walk(item, content_redact=content_redact) for item in value)
    return value
