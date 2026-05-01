"""Telemetry redaction helper."""

from ai.telemetry.redact import RedactSettings, redact_value, scrub_secrets_str


def test_scrub_secrets_strips_email_and_authorization() -> None:
    s = "Contact admin@example.com and use Authorization: Bearer secret-token-here"
    out = scrub_secrets_str(s)
    assert "admin@example.com" not in out
    assert "secret-token" not in out


def test_redact_long_string_when_prompts_redacted() -> None:
    settings = RedactSettings(redact_prompts=True, redact_tool_args=True)
    long = "x" * 40
    v = redact_value(long, settings, mode="prompt")
    assert isinstance(v, dict)
    assert v.get("len") == 40
    assert v.get("sha256_16")


def test_redact_respects_prompts_off() -> None:
    settings = RedactSettings(redact_prompts=False, redact_tool_args=False)
    long = "y" * 40
    v = redact_value(long, settings, mode="prompt")
    assert v == "y" * 40


def test_sensitive_keys_always_redacted() -> None:
    settings = RedactSettings(redact_prompts=False, redact_tool_args=False)
    v = redact_value({"Authorization": "Bearer x", "ok": "short"}, settings, mode="general")
    assert v["Authorization"] == "[redacted]"
    assert v["ok"] == "short"
