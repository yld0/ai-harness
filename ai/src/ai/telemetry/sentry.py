""" Sentry. """

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from ai.config import TelemetryConfig
from ai.config import telemetry_config, config
from ai.telemetry.redact import redact_settings_from_env, redact_value

logger = logging.getLogger(__name__)


def _breadcrumb_processor(data: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    settings = redact_settings_from_env()
    if "message" in data and isinstance(data["message"], str):
        data["message"] = str(redact_value(data["message"], settings, mode="general"))
    if "data" in data and data["data"] is not None:
        data["data"] = redact_value(data["data"], settings, mode="general")
    return data


def init_sentry(telemetry_config: TelemetryConfig | None, *, loader: Callable[[], Any] | None = None) -> None:
    """ Initialize Sentry with the given configuration. """
    dsn = telemetry_config.SENTRY_DSN
    if not dsn:
        logger.info("[STAGE] Sentry DSN not set, skipping initialisation")
        return

    sample_rate = max(0.0, min(1.0, float(telemetry_config.TELEMETRY_SAMPLE_RATE)))
    
    logger.info(f"[STAGE] Initializing Sentry with sample rate {sample_rate}")
    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=sample_rate,
        send_default_pii=False,
        environment=os.getenv("SENTRY_ENV", os.getenv("ENV", "development")),
        integrations=[StarletteIntegration(), FastApiIntegration()],
        before_breadcrumb=_breadcrumb_processor,
        release=os.getenv("IMAGE_TAG"),
        server_name=config.COMPONENT,
    )
