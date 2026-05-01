"""Telemetry integrations (Sentry, PostHog, Langfuse)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ai.telemetry.langfuse import (
    agent_run_observation,
    get_langfuse_client,
    init_langfuse,
    reset_langfuse_client,
)
from ai.telemetry.posthog import (
    capture_event,
    get_posthog_client,
    init_posthog,
    reset_posthog_client,
)
from ai.telemetry.sentry import capture_exception, init_sentry

if TYPE_CHECKING:
    from ai.config import TelemetryConfig


def setup_telemetry(telemetry_cfg: TelemetryConfig | None = None) -> None:
    """Initialize configured backends; no-op when keys/DSN are absent."""
    if telemetry_cfg is None:
        from ai.config import telemetry_config as telemetry_cfg

    reset_posthog_client()
    reset_langfuse_client()
    init_sentry(telemetry_cfg)
    init_posthog(telemetry_cfg)
    init_langfuse(telemetry_cfg)


__all__ = [
    "agent_run_observation",
    "capture_event",
    "capture_exception",
    "get_langfuse_client",
    "get_posthog_client",
    "init_langfuse",
    "init_posthog",
    "init_sentry",
    "reset_langfuse_client",
    "reset_posthog_client",
    "setup_telemetry",
]
