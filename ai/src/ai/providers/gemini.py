"""Gemini provider adapter using google-genai directly."""

import os
from typing import Any

from ai.agent.loop import ToolCall
from ai.providers.base import ProviderRequest, ProviderResponse
from ai.providers.errors import ProviderAuthError, classify_provider_error
from ai.providers.schema_normalize import normalize_for_gemini


class GeminiClient:
    name = "gemini"

    def __init__(self, *, api_key: str | None = None, client: Any | None = None) -> None:
        self.api_key = api_key or os.getenv("GENAI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self._client = client

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        if self._client is None:
            self._client = self._build_client()

        tools = normalize_for_gemini(request.tools)
        try:
            response = await self._client.aio.models.generate_content(
                model=request.model,
                contents=self._contents(request),
                config=self._config(tools, request.request_thinking),
            )
        except Exception as exc:
            raise classify_provider_error(exc, provider=self.name, model=request.model) from exc

        text = getattr(response, "text", "") or ""
        return ProviderResponse(
            text=text,
            tool_calls=self._extract_tool_calls(response),
            usage=self._extract_usage(response),
            provider=self.name,
            raw_ref=getattr(response, "response_id", None),
            finish_reason=self._finish_reason(response),
            thinking_text=(self._extract_thinking(response) if request.request_thinking else None),
            model=request.model,
        )

    def _build_client(self) -> Any:
        if not self.api_key:
            raise ProviderAuthError("GENAI_API_KEY or GOOGLE_API_KEY is not configured", provider=self.name)
        try:
            from google import genai
        except ImportError as exc:
            raise ProviderAuthError("google-genai is not installed", provider=self.name) from exc
        return genai.Client(api_key=self.api_key)

    @staticmethod
    def _contents(request: ProviderRequest) -> list[dict[str, Any]]:
        contents: list[dict[str, Any]] = []
        for message in request.messages:
            if message.role == "system":
                role = "user"
                text = f"System instructions:\n{message.content}"
            elif message.role == "assistant":
                role = "model"
                text = message.content
            else:
                role = "user"
                text = message.content
            contents.append({"role": role, "parts": [{"text": text}]})
        return contents

    @staticmethod
    def _config(tools: list[dict[str, Any]], request_thinking: bool) -> dict[str, Any]:
        config: dict[str, Any] = {}
        if tools:
            config["tools"] = tools
        if request_thinking:
            config["thinking_config"] = {"include_thoughts": True}
        return config

    @staticmethod
    def _extract_tool_calls(response: Any) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", []) or []:
                function_call = getattr(part, "function_call", None)
                if function_call is None:
                    continue
                calls.append(
                    ToolCall(
                        id=getattr(function_call, "id", None) or f"gemini-{len(calls) + 1}",
                        name=getattr(function_call, "name", ""),
                        arguments=dict(getattr(function_call, "args", {}) or {}),
                    )
                )
        return calls

    @staticmethod
    def _extract_usage(response: Any) -> dict[str, Any]:
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            return {}
        return {
            "prompt_tokens": getattr(usage, "prompt_token_count", None),
            "completion_tokens": getattr(usage, "candidates_token_count", None),
            "total_tokens": getattr(usage, "total_token_count", None),
        }

    @staticmethod
    def _finish_reason(response: Any) -> str:
        candidates = getattr(response, "candidates", []) or []
        if not candidates:
            return "stop"
        return str(getattr(candidates[0], "finish_reason", "stop") or "stop").lower()

    @staticmethod
    def _extract_thinking(response: Any) -> str | None:
        thoughts: list[str] = []
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", []) or []:
                thought = getattr(part, "thought", None)
                if thought:
                    thoughts.append(str(thought))
        return "\n".join(thoughts) or None
