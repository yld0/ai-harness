"""add_skill / patch_skill — governance placeholders (Phase 19)."""

from __future__ import annotations

from typing import Any, ClassVar

from ai.tools._base import Tool, ToolResult, err_result
from ai.tools.types import ToolContext
from ai.tools.permissions import PermissionMode

_PHASE_19 = "autonomous skill review (see plans/20-phase-19-autonomous-skill-review.md)"


class AddSkillStub(Tool):
    name: ClassVar[str] = "add_skill"
    description: ClassVar[str] = "Add a new skill to the project skills area (governance not wired in Phase 6)."
    required_permission: ClassVar[PermissionMode] = PermissionMode.WorkspaceWrite
    file_component_risk: ClassVar[bool] = False

    @property
    def parameters_json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "content": {"type": "string"},
            },
        }

    async def _execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        return err_result(
            "governance_not_configured",
            "Skill creation is not enabled until skill governance is configured.",
            hint=f"Wired in Phase 19: {_PHASE_19}.",
        )


class PatchSkillStub(Tool):
    name: ClassVar[str] = "patch_skill"
    description: ClassVar[str] = "Update an existing skill (governance not wired in Phase 6)."
    required_permission: ClassVar[PermissionMode] = PermissionMode.WorkspaceWrite
    file_component_risk: ClassVar[bool] = False

    @property
    def parameters_json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "patch": {"type": "string", "description": "Diff or new body"},
            },
        }

    async def _execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        return err_result(
            "governance_not_configured",
            "Skill updates are not enabled until skill governance is configured.",
            hint=f"Wired in Phase 19: {_PHASE_19}.",
        )
