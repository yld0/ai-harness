"""Abstract tool, JSON results, and OpenAI function definitions."""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar, Literal, TypedDict

from ai.agent.prompt_builder import Channel
from ai.tools.types import ToolContext
from ai.tools.permissions import PermissionMode, allows


@dataclass(frozen=True, slots=True)
class ToolResult:
    ok: bool
    data: Any = None
    error: dict[str, Any] | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "ok": self.ok,
                **({"data": self.data} if self.ok else {}),
                **({"error": self.error} if not self.ok and self.error else {}),
            },
            sort_keys=True,
            default=str,
        )


class OpenAIFunctionDef(TypedDict, total=False):
    type: Literal["function"]
    function: dict[str, Any]


def err_result(code: str, message: str, *, hint: str | None = None) -> ToolResult:
    err: dict[str, Any] = {"code": code, "message": message}
    if hint:
        err["hint"] = hint
    return ToolResult(ok=False, error=err)


def ok_result(data: Any) -> ToolResult:
    return ToolResult(ok=True, data=data)


class Tool(ABC):
    """
    Async tool with JSON schema, permission gating, and CoT tool_start/tool_done.

    Args:
        name: The name of the tool.
        description: The description of the tool.
        required_permission: The permission required to use the tool.
        hidden_channels: The channels on which the tool is not available.
        file_component_risk: Whether the tool is risky to use on file components.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    required_permission: ClassVar[PermissionMode] = PermissionMode.ReadOnly
    hidden_channels: ClassVar[frozenset[Channel]] = frozenset()
    file_component_risk: ClassVar[bool] = True

    @property
    @abstractmethod
    def parameters_json_schema(self) -> dict[str, Any]: ...

    def openai_tool(self) -> OpenAIFunctionDef:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_json_schema,
            },
        }

    @abstractmethod
    async def _execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult: ...

    async def run(self, ctx: ToolContext, args: dict[str, Any]) -> str:
        session = ctx.session_permission
        if not allows(session, self.required_permission):
            return err_result(
                "permission_denied",
                f"Tool {self.name} requires {self.required_permission.name} session permission; current session is {session}.",
            ).to_json()
        if self.file_component_risk and ctx.channel in self.hidden_channels:
            return err_result(
                "channel_blocked",
                f"Tool {self.name} is not available on channel {ctx.channel!r}.",
            ).to_json()
        run_id = str(uuid.uuid4())[:8]
        start_label = f"Running {self.name}…"
        await ctx.emit_cot(
            step_id=f"{self.name}-start-{run_id}",
            step_type="tool_start",
            tool=self.name,
            label=start_label,
            status="active",
        )
        try:
            result = await self._execute(ctx, args)
        except Exception as exc:  # noqa: BLE001
            result = err_result("tool_error", f"{type(exc).__name__}: {exc}")
        finally:
            await ctx.emit_cot(
                step_id=f"{self.name}-done-{run_id}",
                step_type="tool_done",
                tool=self.name,
                label=f"Finished {self.name}.",
                status="complete",
            )
        if isinstance(result, str):
            return result
        return result.to_json()
