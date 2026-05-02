"""PostHog product analytics — optional when ``POSTHOG_API_KEY`` is unset."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from ai.config import TelemetryConfig
from ai.telemetry.redact import redact_settings_from_env, redact_value

_posthog_client: Any | None = None


def get_posthog_client() -> Any | None:
    return _posthog_client


def init_posthog(
    telemetry_config: TelemetryConfig | None = None,
    *,
    factory: Callable[..., Any] | None = None,
) -> None:
    global _posthog_client
    key = ((telemetry_config.POSTHOG_API_KEY if telemetry_config else "") or os.getenv("POSTHOG_API_KEY", "")).strip()
    if not key:
        _posthog_client = None
        return
    host = ((telemetry_config.POSTHOG_HOST if telemetry_config else "") or os.getenv("POSTHOG_HOST", "") or "https://app.posthog.com").strip()
    if factory is not None:
        _posthog_client = factory(project_api_key=key, host=host)
        return
    from posthog import Posthog

    _posthog_client = Posthog(project_api_key=key, host=host)


def capture_event(distinct_id: str, event: str, properties: dict[str, Any] | None = None) -> None:
    """Capture a product event; distinct id should be JWT ``sub``."""
    if _posthog_client is None:
        return
    settings = redact_settings_from_env()
    props = redact_value(properties or {}, settings, mode="general")
    _posthog_client.capture(distinct_id=distinct_id, event=event, properties=props)


def reset_posthog_client() -> None:
    global _posthog_client
    if _posthog_client is not None and hasattr(_posthog_client, "shutdown"):
        try:
            _posthog_client.shutdown()
        except Exception:
            pass
    _posthog_client = None
