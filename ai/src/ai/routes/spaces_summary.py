"""Route handler: spaces-summary.

Generates a styled report from a space's knowledge-base.md and items.yaml,
writing it to reports/<style>/<ISO-timestamp>.md.

Input keys:
  - ``space_id``: str — required.
  - ``style``: str — one of: report, deep_report, key_takeaways, blog_post, tldr, summary.
              Defaults to "summary".
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from ai.routes.context import RouteContext, RouteResult

logger = logging.getLogger(__name__)

ReportStyle = Literal["report", "deep_report", "key_takeaways", "blog_post", "tldr", "summary"]

_VALID_STYLES: frozenset[str] = frozenset({"report", "deep_report", "key_takeaways", "blog_post", "tldr", "summary"})

_STYLE_INSTRUCTIONS: dict[str, str] = {
    "report": "Write a structured analytical report with sections: Executive Summary, Key Findings, Analysis, Conclusion.",
    "deep_report": "Write a comprehensive deep-dive report covering background, current state, risks, opportunities, and outlook.",
    "key_takeaways": "List the 5–7 most important takeaways in bullet-point format, each with a one-line explanation.",
    "blog_post": "Write an engaging, readable blog post suitable for a general audience with a strong title and conclusion.",
    "tldr": "Write a TLDR of ≤150 words. Lead with the single most important fact.",
    "summary": "Write a concise 2–4 paragraph executive summary covering what the space is about and the key current state.",
}

_REPORT_PROMPT_TEMPLATE = """\
You are a research synthesis assistant.

Knowledge base for space "{space_id}":
---
{kb_content}
---

Task: {style_instruction}
"""


async def run(ctx: RouteContext) -> RouteResult:
    space_id = ctx.input.get("space_id")
    if not space_id:
        return RouteResult(text="space_id is required.", ok=False, error="missing_input")

    style: str = ctx.input.get("style", "summary")
    if style not in _VALID_STYLES:
        return RouteResult(
            text=f"Invalid style {style!r}. Must be one of: {', '.join(sorted(_VALID_STYLES))}.",
            ok=False,
            error="invalid_style",
        )

    try:
        space_dir = ctx.layout.entity_dir(ctx.user_id, "spaces", space_id)
    except Exception as exc:
        return RouteResult(text=f"Invalid space_id: {exc}", ok=False, error="invalid_space_id")

    kb_path = space_dir / "knowledge-base.md"
    kb_content = kb_path.read_text("utf-8") if kb_path.is_file() else "(no knowledge base yet)"

    style_instruction = _STYLE_INSTRUCTIONS[style]
    prompt = _REPORT_PROMPT_TEMPLATE.format(
        space_id=space_id,
        kb_content=kb_content[:6000],
        style_instruction=style_instruction,
    )

    try:
        report_text = await ctx.call_llm(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.exception("spaces-summary: LLM call failed")
        return RouteResult(text=f"Report generation failed: {exc}", ok=False, error="llm_error")

    # Persist report to reports/<style>/<ISO-timestamp>.md
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H-%M-%SZ")
    report_dir = space_dir / "reports" / style
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{timestamp}.md"
    report_path.write_text(report_text, encoding="utf-8")

    return RouteResult(
        text=report_text,
        metadata={
            "space_id": space_id,
            "style": style,
            "report_path": str(report_path),
            "generated_at": now.isoformat(),
        },
    )
