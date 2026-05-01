"""Bridge: spaces_* ↔ knowledge-base.md  (GQL is source of truth).

Pull: fetch ``spaces_spaces``, write each space's instructions to
``users/<uid>/life/spaces/<space_id>/knowledge-base.md``.

Push: read knowledge-base.md, call ``spaces_updateSpace`` to sync back.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from ai.memory.bridges.base import Bridge, PullResult, PushResult
from ai.memory.para import ParaMemoryLayout

logger = logging.getLogger(__name__)

SPACES_QUERY = """
query GetSpaces {
  spaces_spaces {
    spaces {
      id
      spaceID
      title
      description
      instructions
    }
    returnedCount
  }
}
"""

UPDATE_SPACE_MUTATION = """
mutation UpdateSpace($id: String!, $instructions: String) {
  spaces_updateSpace(id: $id, instructions: $instructions) {
    id
  }
}
"""


class SpacesBridge(Bridge):
    """GQL-wins bridge for spaces knowledge-base."""

    direction = "both"
    gql_surface = "spaces"
    conflict_rule = "gql_wins"

    async def pull(
        self,
        user_id: str,
        bearer_token: str,
        *,
        layout: ParaMemoryLayout,
        client: Optional[Any] = None,
    ) -> PullResult:
        from ai.tools.graphql import GraphqlClient

        gql: Any = client or GraphqlClient()
        try:
            data = await gql.execute(SPACES_QUERY, bearer_token=bearer_token)
        except Exception as exc:  # noqa: BLE001
            logger.warning("spaces_* pull failed for user %s: %s", user_id, exc)
            return PullResult(ok=False, detail=str(exc), error=str(exc))

        raw_spaces: list[dict] = (data.get("spaces_spaces") or {}).get("spaces") or []
        written = 0
        for space in raw_spaces:
            if not isinstance(space, dict):
                continue
            space_id = space.get("spaceID") or space.get("id") or ""
            if not space_id:
                continue
            try:
                kb_path = layout.entity_dir(user_id, "spaces", space_id) / "knowledge-base.md"
                kb_path.parent.mkdir(parents=True, exist_ok=True)
                _write_knowledge_base(kb_path, space)
                written += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("failed to write knowledge-base for space %s: %s", space_id, exc)

        return PullResult(ok=True, records_written=written)

    async def push(
        self,
        file_path: Path,
        user_id: str,
        bearer_token: str,
        *,
        layout: ParaMemoryLayout,
        client: Optional[Any] = None,
    ) -> PushResult:
        if not file_path.is_file():
            return PushResult(ok=True, detail="file_not_found")

        # Derive space_id from path (…/spaces/<space_id>/knowledge-base.md)
        space_id = file_path.parent.name
        content = file_path.read_text(encoding="utf-8")

        from ai.tools.graphql import GraphqlClient

        gql: Any = client or GraphqlClient()
        try:
            await gql.execute(
                UPDATE_SPACE_MUTATION,
                variables={"id": space_id, "instructions": content},
                bearer_token=bearer_token,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("spaces push failed for space %s: %s", space_id, exc)
            return PushResult(ok=False, detail=str(exc), error=str(exc))

        return PushResult(ok=True, records_pushed=1)


def _write_knowledge_base(path: Path, space: dict[str, Any]) -> None:
    title = space.get("title") or "(untitled space)"
    description = space.get("description") or ""
    instructions = space.get("instructions") or ""
    lines = [f"# {title}"]
    if description:
        lines.append(f"\n{description}")
    if instructions:
        lines.append(f"\n## Instructions\n\n{instructions}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
