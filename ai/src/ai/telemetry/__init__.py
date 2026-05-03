"""Telemetry integrations (Sentry, PostHog, Langfuse)."""

from __future__ import annotations

from ai.config import TelemetryConfig, telemetry_config
from ai.telemetry.langfuse import init_langfuse, reset_langfuse_client
from ai.telemetry.posthog import init_posthog, reset_posthog_client
from ai.telemetry.sentry import init_sentry


def init_telemetry(telemetry_cfg: TelemetryConfig | None = telemetry_config) -> None:
    """Initialize configured backends; no-op when keys/DSN are absent."""
    init_sentry(telemetry_cfg)
    init_posthog(telemetry_cfg)
    init_langfuse(telemetry_cfg)
