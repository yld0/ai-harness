"""Bridge: memories_* (Neo4j) — pull-only into prompt block.

Fetches the user's stored Neo4j memories and returns them as a
``## Graph memories`` subsection injected into the prompt's
``<memory-context>`` block by ``memory.merge``.  No file mirror is written.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from ai.clients.memories import fetch_memories
from ai.memory.bridges.base import Bridge, PullResult, PushResult
from ai.memory.para import ParaMemoryLayout
from ai.memory.threat_scan import MemoryThreatError, scan_memory_text

logger = logging.getLogger(__name__)

_MAX_MEMORY_CHARS = 8_000  # budget cap before threat-scan truncation


class MemoriesBridge(Bridge):
    """Pull user memories from Neo4j GraphQL and surface in the prompt."""

    direction = "pull"
    gql_surface = "memories"
    conflict_rule = "gql_wins"

    async def pull(
        self,
        user_id: str,
        bearer_token: str,
        *,
        layout: ParaMemoryLayout,
        client: Optional[Any] = None,
    ) -> PullResult:
        try:
            records = await fetch_memories(bearer_token, client=client)
        except Exception as exc:  # noqa: BLE001
            logger.warning("memories_* pull failed for user %s: %s", user_id, exc)
            return PullResult(ok=False, detail=str(exc), error=str(exc))

        if not records:
            return PullResult(ok=True, records_written=0, detail="empty", prompt_block="")

        lines: list[str] = []
        for item in records:
            text = item["memory"]
            if not text:
                continue
            mid = item.get("memory_id") or ""
            ts = item["updated_at"] or item["created_at"]
            lines.append(f"- [{str(mid)[:8]}] {text}" + (f"  *(updated {ts})*" if ts else ""))

        block = "\n".join(lines)
        try:
            scan_memory_text(block, source="memories_gql")
        except MemoryThreatError as exc:
            logger.warning(
                "memories_* prompt injection detected for user %s: %s; block suppressed",
                user_id,
                exc,
            )
            return PullResult(ok=False, detail="injection_detected", error="injection_detected")

        if len(block) > _MAX_MEMORY_CHARS:
            block = block[:_MAX_MEMORY_CHARS].rstrip() + "\n[truncated]"

        return PullResult(
            ok=True,
            records_written=len(lines),
            prompt_block=block,
        )
