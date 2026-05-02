""" PostHog product analytics — optional when ``POSTHOG_API_KEY`` is unset. """

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from typing import Protocol

from posthog import Posthog

from ai.config import TelemetryConfig
from ai.telemetry.redact import redact_settings_from_env, redact_value

logger = logging.getLogger(__name__)


class _PosthogClient(Protocol):
    def capture(self, *, distinct_id: str, event: str, properties: object) -> None: ...


_posthog_client: _PosthogClient | None = None


def get_posthog_client() -> _PosthogClient | None:
    return _posthog_client


def init_posthog(
    telemetry_config: TelemetryConfig | None = None,
    *,
    factory: Callable[..., _PosthogClient] | None = None,
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

    _posthog_client = Posthog(project_api_key=key, host=host)


def capture_event(distinct_id: str, event: str, properties: Mapping[str, object] | None = None) -> None:
    """ Capture a product event; distinct id should be JWT ``sub``. """
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
            logger.exception("PostHog client shutdown failed")
    _posthog_client = None
