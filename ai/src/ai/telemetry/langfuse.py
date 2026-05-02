"""Langfuse LLM tracing — optional when keys are unset."""

from __future__ import annotations

import os
from contextlib import ExitStack, contextmanager
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ai.agent.loop import (
    Provider,
    ProviderMessage,
    ProviderTurn,
    ToolCall,
    ToolRegistry,
    ToolHandler,
)
from ai.config import TelemetryConfig
from ai.telemetry.redact import RedactSettings, redact_value, scrub_secrets_str

if TYPE_CHECKING:
    from ai.tools.types import ToolContext


def _default_langfuse_class() -> type[Any]:
    from langfuse import Langfuse

    return Langfuse


_langfuse_client: Any | None = None


def get_langfuse_client() -> Any | None:
    return _langfuse_client


def init_langfuse(
    telemetry_config: TelemetryConfig | None = None,
    *,
    factory: Callable[[], type[Any]] | None = None,
) -> None:
    global _langfuse_client
    public = ((telemetry_config.LANGFUSE_PUBLIC_KEY if telemetry_config else "") or os.getenv("LANGFUSE_PUBLIC_KEY", "")).strip()
    secret = ((telemetry_config.LANGFUSE_SECRET_KEY if telemetry_config else "") or os.getenv("LANGFUSE_SECRET_KEY", "")).strip()
    if not public or not secret:
        _langfuse_client = None
        return
    host = ((telemetry_config.LANGFUSE_HOST if telemetry_config else "") or os.getenv("LANGFUSE_HOST", "") or "https://cloud.langfuse.com").strip()
    cls = (factory or _default_langfuse_class)()
    _langfuse_client = cls(public_key=public, secret_key=secret, host=host)


def reset_langfuse_client() -> None:
    global _langfuse_client
    if _langfuse_client is not None and hasattr(_langfuse_client, "shutdown"):
        try:
            _langfuse_client.shutdown()
        except Exception:
            pass
    _langfuse_client = None


def _clip(s: str, max_len: int = 200) -> str:
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


@contextmanager
def agent_run_observation(
    lf: Any | None,
    *,
    user_id: str,
    session_id: str,
    trace_name: str,
    input_summary: dict[str, Any],
):
    if lf is None:
        yield
        return
    from langfuse import propagate_attributes
    from langfuse.types import TraceContext

    trace_id = lf.create_trace_id()
    tc = TraceContext(trace_id=trace_id)
    stack = ExitStack()
    try:
        stack.enter_context(
            lf.start_as_current_observation(
                trace_context=tc,
                name=trace_name,
                as_type="agent",
                input=input_summary,
            )
        )
        stack.enter_context(
            propagate_attributes(
                user_id=_clip(user_id),
                session_id=_clip(session_id),
                trace_name=_clip(trace_name),
            )
        )
        yield
    finally:
        stack.close()


def redact_messages_for_langfuse(messages: list[ProviderMessage], settings: RedactSettings) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        entry: dict[str, Any] = {
            "role": m.role,
            "content": redact_value(m.content, settings, mode="prompt"),
        }
        if m.tool_calls:
            entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": redact_value(tc.arguments, settings, mode="tool_args"),
                }
                for tc in m.tool_calls
            ]
        if m.name:
            entry["name"] = m.name
        if m.tool_call_id:
            entry["tool_call_id"] = m.tool_call_id
        out.append(entry)
    return out


class LangfuseProviderWrapper:
    """Child Langfuse generation span around each provider call."""

    def __init__(self, inner: Provider, lf: Any, settings: RedactSettings) -> None:
        self._inner = inner
        self._lf = lf
        self._settings = settings

    async def complete(self, messages: list[ProviderMessage], *, tools_enabled: bool, effort: str) -> ProviderTurn:
        if self._lf is None:
            return await self._inner.complete(messages, tools_enabled=tools_enabled, effort=effort)
        inp = redact_messages_for_langfuse(messages, self._settings)
        with self._lf.start_as_current_observation(
            name="provider.completion",
            as_type="generation",
            input=inp,
            metadata={"tools_enabled": tools_enabled, "effort": effort},
        ) as gen:
            turn = await self._inner.complete(messages, tools_enabled=tools_enabled, effort=effort)
            meta = turn.metadata if isinstance(turn.metadata, dict) else {}
            usage = meta.get("usage") if isinstance(meta.get("usage"), dict) else {}
            usage_details: dict[str, int] = {}
            for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                v = usage.get(k)
                if isinstance(v, (int, float)):
                    usage_details[k] = int(v)
            raw_out = turn.content
            if self._settings.redact_prompts:
                out_payload: Any = redact_value(raw_out, self._settings, mode="prompt")
            else:
                out_payload = scrub_secrets_str(raw_out)
            gen.update(
                output=out_payload,
                model=str(meta.get("model") or meta.get("provider") or ""),
                usage_details=usage_details or None,
            )
            return turn

    def with_options(self, **kwargs: Any) -> LangfuseProviderWrapper:
        inner = self._inner
        wo = getattr(inner, "with_options", None)
        if callable(wo):
            inner = wo(**kwargs)
        return LangfuseProviderWrapper(inner, self._lf, self._settings)


class LangfuseToolRegistryWrapper:
    """Child Langfuse tool spans for each tool execution."""

    def __init__(self, inner: ToolRegistry, lf: Any, settings: RedactSettings) -> None:
        self._inner = inner
        self._lf = lf
        self._settings = settings

    def register(self, name: str, handler: ToolHandler) -> None:
        self._inner.register(name, handler)

    def has_tool(self, name: str) -> bool:
        return self._inner.has_tool(name)

    async def execute(self, call: ToolCall, ctx: ToolContext) -> str:
        if self._lf is None:
            return await self._inner.execute(call, ctx)
        args_payload = redact_value(call.arguments, self._settings, mode="tool_args")
        with self._lf.start_as_current_observation(
            name=f"tool.{call.name}",
            as_type="tool",
            input={"name": call.name, "arguments": args_payload},
        ) as span:
            result = await self._inner.execute(call, ctx)
            if self._settings.redact_prompts:
                out: Any = redact_value(result, self._settings, mode="prompt")
            else:
                out = scrub_secrets_str(result)
            span.update(output=out)
            return result
