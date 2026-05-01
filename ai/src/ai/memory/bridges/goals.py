"""Bridge: goals_* ↔ goals/  (last-write-wins).

GQL surface: ``Goal`` type exists in the AGENTS subgraph but no list query
root was found in the supergraph.  GQL operations are stubbed; file-side
operations (goal.md + progress.yaml) are fully implemented.

File locations:
  users/<uid>/goals/<goal_id>/goal.md
  users/<uid>/goals/<goal_id>/progress.yaml
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from ai.memory.bridges.base import Bridge, PullResult, PushResult
from ai.memory.para import ParaMemoryLayout

logger = logging.getLogger(__name__)


class GoalsBridge(Bridge):
    """last-write-wins goals bridge.  GQL side stubbed; file side real."""

    direction = "both"
    gql_surface = "goals"
    conflict_rule = "last_write_wins"

    async def pull(
        self,
        user_id: str,
        bearer_token: str,
        *,
        layout: ParaMemoryLayout,
        client: Optional[Any] = None,
    ) -> PullResult:
        logger.debug("goals_* GQL pull: not_implemented (no supergraph query root)")
        return PullResult(ok=False, detail="not_implemented", error="not_implemented")

    async def push(
        self,
        file_path: Path,
        user_id: str,
        bearer_token: str,
        *,
        layout: ParaMemoryLayout,
        client: Optional[Any] = None,
    ) -> PushResult:
        logger.debug("goals_* GQL push: not_implemented (no supergraph mutation found)")
        return PushResult(ok=False, detail="not_implemented", error="not_implemented")

    # ─── File-side helpers ─────────────────────────────────────────────── #

    @staticmethod
    def write_goal(
        layout: ParaMemoryLayout,
        user_id: str,
        goal_id: str,
        *,
        description: str,
        status: str = "active",
        provenance: str = "file",
        difficulty: str = "medium",
        success_criteria: Optional[list[str]] = None,
        sub_goal_ids: Optional[list[str]] = None,
        updated_at: Optional[str] = None,
    ) -> tuple[Path, Path]:
        """Write goal.md and progress.yaml; return (goal_path, progress_path)."""
        goal_dir = layout.guarded_user_path(user_id, "goals", goal_id)
        goal_dir.mkdir(parents=True, exist_ok=True)

        # goal.md
        goal_md = goal_dir / "goal.md"
        goal_md.write_text(
            f"# Goal: {goal_id}\n\n{description}\n",
            encoding="utf-8",
        )

        # progress.yaml
        ts = updated_at or datetime.now(timezone.utc).isoformat()
        progress: dict[str, Any] = {
            "goal_id": goal_id,
            "description": description,
            "status": status,
            "provenance": provenance,
            "difficulty": difficulty,
            "created_at": ts,
            "updated_at": ts,
            "success_criteria": success_criteria or [],
            "sub_goal_ids": sub_goal_ids or [],
        }
        progress_yaml = goal_dir / "progress.yaml"
        with progress_yaml.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(progress, fh, default_flow_style=False, allow_unicode=True)

        return goal_md, progress_yaml

    @staticmethod
    def read_goal(layout: ParaMemoryLayout, user_id: str, goal_id: str) -> dict[str, Any]:
        """Read progress.yaml for a goal; returns {} if missing."""
        progress_yaml = layout.guarded_user_path(user_id, "goals", goal_id, "progress.yaml")
        if not progress_yaml.is_file():
            return {}
        with progress_yaml.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    @staticmethod
    def resolve_conflict(local: dict[str, Any], remote: dict[str, Any]) -> dict[str, Any]:
        """last-write-wins: compare updated_at timestamps."""
        local_ts = local.get("updated_at") or local.get("updatedAt") or ""
        remote_ts = remote.get("updated_at") or remote.get("updatedAt") or ""
        return remote if remote_ts > local_ts else local
