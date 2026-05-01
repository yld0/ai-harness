"""Merge PARA hot snapshot with memories_* Neo4j graph block under budget.

The ``memories_*`` bridge returns a plain-text block of Neo4j memories.
``merge_memory_with_graph`` injects that block as a ``## Graph memories``
subsection inside the existing ``<memory-context>…</memory-context>`` fence,
respecting the Phase 4 character budget.

If the memories_* pull fails (offline, token absent, injection detected) the
function returns the PARA snapshot unchanged — the agent degrades gracefully
to PARA-only context.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, TYPE_CHECKING

from ai.memory.bridges.registry import get_bridge
from ai.memory.budget import DEFAULT_MEMORY_BUDGET_CHARS

if TYPE_CHECKING:
    from ai.memory.bridges.base import Bridge
    from ai.memory.schemas import HotMemorySnapshot
    from ai.memory.para import ParaMemoryLayout

logger = logging.getLogger(__name__)

_CLOSE_TAG = "</memory-context>"
_GRAPH_HEADING = "\n\n## Graph memories\n"


def _inject_graph_block(para_content: str, graph_block: str, budget_chars: int) -> str:
    """Insert *graph_block* before the closing </memory-context> tag.

    Truncates the block if it would push total size past *budget_chars*.
    """
    if not graph_block:
        return para_content

    available = budget_chars - len(para_content) - len(_GRAPH_HEADING) - 5
    if available < 50:
        logger.debug("no budget for graph memories (%d chars available)", available)
        return para_content

    trimmed = graph_block[:available]
    if len(graph_block) > available:
        trimmed = trimmed.rstrip() + "\n[truncated]"

    insertion = _GRAPH_HEADING + trimmed

    if _CLOSE_TAG in para_content:
        return para_content.replace(_CLOSE_TAG, insertion + "\n" + _CLOSE_TAG, 1)
    return para_content + insertion


async def merge_memory_with_graph(
    *,
    para_snapshot: "HotMemorySnapshot",
    layout: "ParaMemoryLayout",
    user_id: str,
    bearer_token: Optional[str],
    memories_bridge: Optional["Bridge"] = None,
    budget_chars: int = DEFAULT_MEMORY_BUDGET_CHARS,
    client: Optional[Any] = None,
) -> str:
    """Return the merged memory string for insertion into the system prompt.

    Args:
        para_snapshot:    The PARA hot snapshot (already fetched/cached).
        layout:           Memory layout for path resolution.
        user_id:          Caller's user identifier.
        bearer_token:     JWT for GraphQL authentication.
        memories_bridge:  Optional pre-configured MemoriesBridge instance.
                          Defaults to the registered ``"memories"`` bridge.
        budget_chars:     Total character budget for the merged block.
        client:           Optional GraphQL client override (for tests).

    Returns the merged ``<memory-context>…</memory-context>`` string.  Falls
    back to the PARA snapshot on any error.
    """
    base = para_snapshot.content

    if not bearer_token:
        return base

    # Resolve bridge
    bridge = memories_bridge
    if bridge is None:
        bridge = get_bridge("memories")

    if bridge is None:
        return base

    try:
        result = await bridge.pull(user_id, bearer_token, layout=layout, client=client)
    except Exception as exc:  # noqa: BLE001
        logger.warning("memories_* merge failed for user %s: %s", user_id, exc)
        return base

    if not result.ok or not result.prompt_block:
        return base

    return _inject_graph_block(base, result.prompt_block, budget_chars)
