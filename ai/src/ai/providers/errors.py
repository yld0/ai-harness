"""Typed provider errors and retry classification."""

from dataclasses import dataclass
from typing import Literal

ProviderErrorKind = Literal["rate_limit", "context_overflow", "auth", "unknown"]


@dataclass
class ProviderError(Exception):
    message: str
    kind: ProviderErrorKind = "unknown"
    provider: str | None = None
    model: str | None = None
    retryable: bool = True

    def __str__(self) -> str:
        prefix = f"{self.provider or 'provider'}:{self.model or 'unknown'}"
        return f"{prefix} {self.kind}: {self.message}"


class ProviderRateLimitError(ProviderError):
    def __init__(self, message: str, *, provider: str | None = None, model: str | None = None) -> None:
        super().__init__(message, kind="rate_limit", provider=provider, model=model, retryable=True)


class ProviderContextOverflowError(ProviderError):
    def __init__(self, message: str, *, provider: str | None = None, model: str | None = None) -> None:
        super().__init__(
            message,
            kind="context_overflow",
            provider=provider,
            model=model,
            retryable=True,
        )


class ProviderAuthError(ProviderError):
    def __init__(self, message: str, *, provider: str | None = None, model: str | None = None) -> None:
        super().__init__(message, kind="auth", provider=provider, model=model, retryable=False)


def classify_provider_error(exc: Exception, *, provider: str | None = None, model: str | None = None) -> ProviderError:
    if isinstance(exc, ProviderError):
        if exc.provider is None:
            exc.provider = provider
        if exc.model is None:
            exc.model = model
        return exc

    status_code = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    text = str(exc).lower()
    if status_code == 429 or "rate limit" in text or "too many requests" in text:
        return ProviderRateLimitError(str(exc), provider=provider, model=model)
    if status_code in {401, 403} or "api key" in text or "unauthorized" in text:
        return ProviderAuthError(str(exc), provider=provider, model=model)
    if status_code == 400 and ("context" in text or "token" in text):
        return ProviderContextOverflowError(str(exc), provider=provider, model=model)
    if "context length" in text or "maximum context" in text:
        return ProviderContextOverflowError(str(exc), provider=provider, model=model)
    return ProviderError(str(exc), kind="unknown", provider=provider, model=model, retryable=True)
