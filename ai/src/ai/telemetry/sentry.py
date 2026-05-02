"""Sentry error reporting — optional when ``SENTRY_DSN`` is unset."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from ai.config import TelemetryConfig
from ai.telemetry.redact import redact_settings_from_env, redact_value


def _load_sentry() -> Any:
    import sentry_sdk

    return sentry_sdk


def _breadcrumb_processor(data: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    settings = redact_settings_from_env()
    if "message" in data and isinstance(data["message"], str):
        data["message"] = str(redact_value(data["message"], settings, mode="general"))
    if "data" in data and data["data"] is not None:
        data["data"] = redact_value(data["data"], settings, mode="general")
    return data


def init_sentry(
    telemetry_config: TelemetryConfig | None = None,
    *,
    loader: Callable[[], Any] | None = None,
) -> None:
    dsn = ((telemetry_config.SENTRY_DSN if telemetry_config else "") or os.getenv("SENTRY_DSN", "")).strip()
    if not dsn:
        return
    sdk = (loader or _load_sentry)()
    sample_raw = (str(telemetry_config.TELEMETRY_SAMPLE_RATE) if telemetry_config else os.getenv("TELEMETRY_SAMPLE_RATE", "1.0")).strip() or "1.0"
    sample = max(0.0, min(1.0, float(sample_raw)))
    component = (telemetry_config.COMPONENT if telemetry_config else os.getenv("COMPONENT", "ai")).strip() or "ai"

    try:
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except Exception:  # pragma: no cover - optional extras
        integrations: list[Any] = []
    else:
        integrations = [StarletteIntegration(), FastApiIntegration()]

    sdk.init(
        dsn=dsn,
        traces_sample_rate=sample,
        send_default_pii=False,
        environment=os.getenv("SENTRY_ENV", os.getenv("ENV", "development")),
        integrations=integrations,
        before_breadcrumb=_breadcrumb_processor,
        release=os.getenv("IMAGE_TAG") or None,
        server_name=component,
    )


def capture_exception(exc: BaseException | None = None, **kwargs: Any) -> None:
    """Test-friendly wrapper around ``sentry_sdk.capture_exception``."""
    try:
        import sentry_sdk
    except Exception:
        return
    sentry_sdk.capture_exception(exc, **kwargs)
