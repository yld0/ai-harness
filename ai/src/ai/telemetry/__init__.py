""" Telemetry integrations (Sentry, PostHog, Langfuse). """

from __future__ import annotations

from ai.config import TelemetryConfig, telemetry_config
from ai.telemetry.langfuse import init_langfuse, reset_langfuse_client
from ai.telemetry.posthog import init_posthog, reset_posthog_client
from ai.telemetry.sentry import init_sentry


def setup_telemetry(telemetry_cfg: TelemetryConfig | None = None) -> None:
    """ Initialize configured backends; no-op when keys/DSN are absent. """
    if telemetry_cfg is None:
        telemetry_cfg = telemetry_config

    reset_posthog_client()
    reset_langfuse_client()
    init_sentry(telemetry_cfg)
    init_posthog(telemetry_cfg)
    init_langfuse(telemetry_cfg)
