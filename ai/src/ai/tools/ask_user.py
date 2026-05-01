"""AskUser / clarification bridge — returns structured follow-up for the client."""

from __future__ import annotations

from typing import Any, ClassVar

from ai.tools.base import Tool, ToolResult, err_result, ok_result
from ai.tools.context import ToolContext


class AskUserTool(Tool):
    name: ClassVar[str] = "ask_user"
    description: ClassVar[str] = (
        "Request clarification from the user. Returns a machine-readable question payload; "
        "the host should surface a UI prompt and resume the turn with the answer."
    )
    file_component_risk: ClassVar[bool] = False

    @property
    def parameters_json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "choices": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of short choices for UI buttons",
                },
            },
            "required": ["question"],
        }

    async def _execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        q = str(args.get("question", ""))
        if not q:
            return err_result("invalid_argument", "question is required")
        choices = args.get("choices")
        if choices is not None and not isinstance(choices, list):
            return err_result("invalid_argument", "choices must be a list of strings when provided")
        payload = {
            "kind": "ask_user",
            "question": q,
            "choices": list(choices) if isinstance(choices, list) else None,
        }
        return ok_result(payload)
