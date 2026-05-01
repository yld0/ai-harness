"""Autonomous skill review runner (Phase 19).

Extracts tool call patterns from a conversation, optionally calls the LLM to
propose a new skill, and writes a `proposed-<timestamp>.md` file into the user's
`skill_review_queue/` directory under the path-jailed memory root.
"""

from __future__ import annotations

import importlib.resources
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

# Maximum number of tool-call messages to include in the LLM prompt.
_MAX_TOOL_SAMPLES = 20

LLMCaller = Callable[[str], Awaitable[str]]


def _extract_tool_samples(messages: list[Any], max_k: int = _MAX_TOOL_SAMPLES) -> list[str]:
    """Return up to *max_k* tool-call names/errors from the message list.

    Looks for ProviderMessage objects with role="tool"; falls back to dict
    access so tests can pass plain dicts without importing agent internals.
    """
    samples: list[str] = []
    for msg in messages:
        role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else None)
        if role != "tool":
            continue
        name = getattr(msg, "name", None) or (msg.get("name") if isinstance(msg, dict) else None)
        content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else "")
        label = name or "unknown_tool"
        # Flag obvious errors so the LLM can learn what went wrong.
        if isinstance(content, str) and ("error" in content.lower() or "exception" in content.lower()):
            label = f"{label} [error]"
        samples.append(label)
        if len(samples) >= max_k:
            break
    return samples


def _build_llm_prompt(
    user_message: str,
    response_text: str,
    tool_samples: list[str],
) -> str:
    joined = "\n".join(f"  - {s}" for s in tool_samples) or "  (none)"
    return (
        "You are a skill librarian. Based on the conversation below, propose a reusable "
        "skill (a short system-prompt fragment) that would help the agent handle similar "
        "requests more efficiently in future.\n\n"
        f"User goal summary: {user_message[:500]}\n\n"
        f"Tool calls used:\n{joined}\n\n"
        "Write the skill as a Markdown section with:\n"
        "1. A concise `name` (slug, no spaces)\n"
        "2. A one-sentence `description`\n"
        "3. A `## Trigger` paragraph (when to activate)\n"
        "4. A `## Prompt / Instructions` section (the skill body)\n"
        "5. One short example\n\n"
        "Keep it under 400 words. Do NOT include YAML frontmatter."
    )


def _render_template(
    *,
    skill_body: str,
    timestamp: str,
    user_id: str,
) -> str:
    """Wrap *skill_body* in the review-queue frontmatter."""
    return (
        f"---\n"
        f"status: pending_review\n"
        f"proposed_at: {timestamp}\n"
        f"proposed_for_user: {user_id}\n"
        f"source: autonomous_skill_review\n"
        f"---\n\n"
        f"{skill_body.strip()}\n\n"
        "---\n\n"
        "<!-- Review notes: Do not merge until manually validated. "
        "Update status to approved before merging into skills/. -->\n"
    )


class ReviewRunner:
    """Writes a `proposed-<timestamp>.md` skill proposal to the user's review queue.

    Parameters
    ----------
    layout:
        `ParaMemoryLayout` for path-jailed writes.  If *None*, uses a default
        layout (respects ``MEMORY_ROOT`` env var).
    call_llm:
        Optional async callable ``(prompt: str) -> str``.  When provided the
        runner makes one LLM call to generate the skill body; when absent a
        scaffold template is written instead.
    """

    def __init__(
        self,
        layout: Any | None = None,
        call_llm: LLMCaller | None = None,
    ) -> None:
        self._layout = layout
        self._call_llm = call_llm

    def _get_layout(self) -> Any:
        if self._layout is not None:
            return self._layout
        from ai.memory.para import ParaMemoryLayout  # lazy — keeps tests fast

        return ParaMemoryLayout()

    async def run(
        self,
        *,
        user_id: str,
        user_message: str,
        response_text: str,
        messages: list[Any],
    ) -> Path:
        """Generate a skill proposal and write it; return the written path."""
        layout = self._get_layout()
        tool_samples = _extract_tool_samples(messages)

        if self._call_llm is not None:
            try:
                prompt = _build_llm_prompt(user_message, response_text, tool_samples)
                skill_body = await self._call_llm(prompt)
            except Exception as exc:  # noqa: BLE001
                logger.warning("skill review LLM call failed (%s); using scaffold", exc)
                skill_body = _scaffold_body(tool_samples)
        else:
            skill_body = _scaffold_body(tool_samples)

        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        content = _render_template(skill_body=skill_body, timestamp=timestamp, user_id=user_id)

        dest = layout.guarded_user_path(user_id, "skill_review_queue", f"proposed-{timestamp}.md")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        logger.info("skill review written to %s", dest)
        return dest


def _scaffold_body(tool_samples: list[str]) -> str:
    joined = ", ".join(tool_samples[:10]) or "unknown"
    return (
        f"## Proposed Skill\n\n"
        f"name: auto-proposed-skill\n"
        f"description: Auto-proposed based on tool usage: {joined}\n\n"
        f"## Trigger\n\n"
        f"When the user asks about tasks requiring: {joined}\n\n"
        f"## Prompt / Instructions\n\n"
        f"(Fill in based on the tool call patterns above.)\n\n"
        f"## Examples\n\n"
        f'- Input: "..."\n'
        f'- Expected Output: "..."\n'
    )
