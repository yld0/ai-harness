"""Autonomous skill review proposal writer.

Extract tool call patterns from a conversation, ask an LLM to propose a reusable
skill, and write the proposal into the user's path-jailed review queue.
"""

from __future__ import annotations

import importlib.resources
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai.memory.para import ParaMemoryLayout
from ai.providers.one_shot import LLMCaller, one_shot_caller

logger = logging.getLogger(__name__)

_MAX_TOOL_SAMPLES = 20
_TEMPLATE_NAME = "review_template.md"


def _extract_tool_samples(messages: list[Any], max_k: int = _MAX_TOOL_SAMPLES) -> list[str]:
    """Return up to *max_k* tool-call names/errors from the message list."""

    samples: list[str] = []
    for msg in messages:
        role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else None)
        if role != "tool":
            continue
        name = getattr(msg, "name", None) or (msg.get("name") if isinstance(msg, dict) else None)
        content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else "")
        label = name or "unknown_tool"
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
        f"Assistant response summary: {response_text[:500]}\n\n"
        f"Tool calls used:\n{joined}\n\n"
        "Write the skill as a Markdown section with:\n"
        "1. A concise `name` (slug, no spaces)\n"
        "2. A one-sentence `description`\n"
        "3. A `## Trigger` paragraph (when to activate)\n"
        "4. A `## Prompt / Instructions` section (the skill body)\n"
        "5. One short example\n\n"
        "Keep it under 400 words. Do NOT include YAML frontmatter."
    )


def _load_review_template() -> str:
    """Load the pending-review Markdown template packaged with ai.skills."""

    return importlib.resources.files("ai.skills").joinpath(_TEMPLATE_NAME).read_text(encoding="utf-8")


def _render_template(
    *,
    skill_body: str,
    timestamp: str,
    user_id: str,
) -> str:
    """Render *skill_body* into the pending-review template."""

    return _load_review_template().format(
        timestamp=timestamp,
        user_id=user_id,
        skill_body=skill_body.strip(),
    )


class ReviewRunner:
    """Write an LLM-generated skill proposal to the user's review queue.

    Parameters
    ----------
    layout:
        `ParaMemoryLayout` for path-jailed writes.  If *None*, uses a default
        layout (respects ``MEMORY_ROOT`` env var).
    call_llm:
        Optional async callable ``(prompt: str) -> str`` for tests or custom
        routing.  When absent, the runner uses the configured one-shot provider.
    """

    def __init__(
        self,
        layout: ParaMemoryLayout | None = None,
        call_llm: LLMCaller | None = None,
    ) -> None:
        self._layout = layout
        self._call_llm = call_llm

    def _get_layout(self) -> ParaMemoryLayout:
        if self._layout is not None:
            return self._layout
        return ParaMemoryLayout()

    def _get_llm(self, model_override: str | None) -> LLMCaller:
        if self._call_llm is not None:
            return self._call_llm
        return one_shot_caller(model_override=model_override)

    async def run(
        self,
        *,
        user_id: str,
        user_message: str,
        response_text: str,
        messages: list[Any],
        skill_review_model: str | None = None,
    ) -> Path:
        """Generate a skill proposal and write it; return the written path."""

        layout = self._get_layout()
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest = layout.guarded_user_path(user_id, "skill_review_queue", f"proposed-{timestamp}.md")

        tool_samples = _extract_tool_samples(messages)
        prompt = _build_llm_prompt(user_message, response_text, tool_samples)
        skill_body = (await self._get_llm((skill_review_model or "").strip() or None)(prompt)).strip()

        if not skill_body:
            raise ValueError("skill review LLM returned empty output")

        content = _render_template(skill_body=skill_body, timestamp=timestamp, user_id=user_id)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        logger.info("skill review written to %s", dest)
        return dest
