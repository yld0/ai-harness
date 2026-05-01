"""OpenRouter adapter using the OpenAI-compatible chat API."""

import json
import os
from typing import Any

import httpx

from ai.agent.loop import ToolCall
from ai.providers.base import ProviderRequest, ProviderResponse
from ai.providers.errors import ProviderAuthError, classify_provider_error
from ai.providers.schema_normalize import normalize_for_openai

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterClient:
    name = "openrouter"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        base_url: str = OPENROUTER_URL,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.http_client = http_client
        self.base_url = base_url

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        if not self.api_key:
            raise ProviderAuthError(
                "OPENROUTER_API_KEY is not configured",
                provider=self.name,
                model=request.model,
            )

        owns_client = self.http_client is None
        client = self.http_client or httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))
        try:
            response = await client.post(
                self.base_url,
                headers=self._headers(),
                json=self._payload(request),
            )
            if response.status_code >= 400:
                err = httpx.HTTPStatusError(
                    f"OpenRouter returned {response.status_code}: {response.text}",
                    request=response.request,
                    response=response,
                )
                setattr(err, "status_code", response.status_code)
                raise err
            data = response.json()
        except Exception as exc:
            raise classify_provider_error(exc, provider=self.name, model=request.model) from exc
        finally:
            if owns_client:
                await client.aclose()

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        return ProviderResponse(
            text=self._extract_text(message),
            tool_calls=self._extract_tool_calls(message),
            usage=data.get("usage") or {},
            provider=self.name,
            raw_ref=data.get("id"),
            finish_reason=choice.get("finish_reason") or "stop",
            thinking_text=(self._extract_thinking(message) if request.request_thinking else None),
            model=data.get("model") or request.model,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost"),
            "X-Title": os.getenv("OPENROUTER_APP_NAME", "yld0-ai-harness"),
        }

    @staticmethod
    def _payload(request: ProviderRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [OpenRouterClient._message_payload(message) for message in request.messages],
        }
        if request.tools:
            payload["tools"] = normalize_for_openai(request.tools)
        if request.response_format:
            payload["response_format"] = request.response_format
        return payload

    @staticmethod
    def _message_payload(message: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.role == "tool" and message.tool_call_id:
            payload["tool_call_id"] = message.tool_call_id
        if message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, sort_keys=True),
                    },
                }
                for call in message.tool_calls
            ]
        return payload

    @staticmethod
    def _extract_text(message: dict[str, Any]) -> str:
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") in {
                    "text",
                    "output_text",
                }:
                    parts.append(str(part.get("text") or ""))
            return "".join(parts)
        return ""

    @staticmethod
    def _extract_tool_calls(message: dict[str, Any]) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for raw in message.get("tool_calls") or []:
            function = raw.get("function") or {}
            args = function.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {"raw": args}
            calls.append(
                ToolCall(
                    id=raw.get("id") or f"openrouter-{len(calls) + 1}",
                    name=function.get("name") or "",
                    arguments=dict(args),
                )
            )
        return calls

    @staticmethod
    def _extract_thinking(message: dict[str, Any]) -> str | None:
        if isinstance(message.get("reasoning"), str):
            return message["reasoning"]
        content = message.get("content")
        if isinstance(content, list):
            thoughts = [str(part.get("text") or "") for part in content if isinstance(part, dict) and part.get("type") == "thinking"]
            return "\n".join(thoughts) or None
        return None
