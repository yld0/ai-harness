""" PostHog product analytics — optional when ``POSTHOG_API_KEY`` is unset. """

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Protocol

from posthog import Posthog

from ai.config import TelemetryConfig
from ai.telemetry.redact import RedactSettings, redact_value

logger = logging.getLogger(__name__)


class _PosthogClient(Protocol):
    """ 
    PostHog client protocol. 

    This is a minimal protocol to allow for mocking in tests.

    - Perfect IDE Autocomplete: It explicitly tells your IDE and mypy exactly which method (.capture) you care about and how it should be typed, even if the third-party SDK has loose or messy types.
    - Safer Mocking: It allows you to safely inject a simple MagicMock() in your unit tests without mypy throwing a fit that "a mock is not a real PostHog class instance."
    - Zero Lock-in (Decoupling): Your code only depends on a generic "shape" (anything with a .capture method), so you can swap out PostHog for another analytics tool tomorrow without changing any type hints.
    """
    def capture(self, *, distinct_id: str, event: str, properties: object) -> None: ...


POSTHOG_CLIENT: _PosthogClient | None = None


def get_posthog_client() -> _PosthogClient | None:
    return POSTHOG_CLIENT


def init_posthog(telemetry_config: TelemetryConfig | None = None, *, factory: Callable[..., _PosthogClient] | None = None) -> None:
    global POSTHOG_CLIENT
    key = telemetry_config.POSTHOG_API_KEY

    if not key:
        logger.info("[STAGE] PostHog API key not set, skipping initialisation")
        return

    host = telemetry_config.POSTHOG_HOST

    if factory is not None:
        logger.info("[STAGE] PostHog client factory provided, using factory to create client")
        POSTHOG_CLIENT = factory(project_api_key=key, host=host)
        return

    POSTHOG_CLIENT = Posthog(project_api_key=key, host=host)


def capture_event(distinct_id: str, event: str, properties: Mapping[str, object] | None = None) -> None:
    """ Capture a product event; distinct id should be JWT ``sub``. """

    if POSTHOG_CLIENT is None:
        logger.warning("PostHog client not initialized")
        return

    settings = RedactSettings(
        redact_prompts=True,
        redact_tool_args=True,
    )
    props = redact_value(properties or {}, settings, mode="general")
    POSTHOG_CLIENT.capture(distinct_id=distinct_id, event=event, properties=props)
