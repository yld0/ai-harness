"""Route handler: spaces-youtube-summary.

Generates a structured summary of a YouTube video (or playlist) for a space.
The video content is passed via ``transcript`` or ``url`` in the input; the
handler delegates understanding to the LLM.

Input keys:
  - ``space_id``: str — required.
  - ``url``: str — YouTube URL (informational; transcript fetch deferred).
  - ``transcript``: str — raw transcript text (if pre-fetched).
  - ``title``: str — optional video title for context.
  - ``style``: str — report style (default "key_takeaways").
"""

from __future__ import annotations

import logging

from ai.routes.context import RouteContext, RouteResult

logger = logging.getLogger(__name__)

_YOUTUBE_PROMPT_TEMPLATE = """\
You are a research assistant summarising a YouTube video for a knowledge space.

Space: "{space_id}"
Video title: {title}
Video URL: {url}

Transcript (truncated):
---
{transcript}
---

Task: {style_instruction}

Also append a section "## Key Quotes" with 2–3 verbatim quotes from the transcript.
"""

_STYLE_INSTRUCTIONS: dict[str, str] = {
    "key_takeaways": "List the 5 most important takeaways in bullet-point format.",
    "summary": "Write a 3-paragraph executive summary.",
    "tldr": "Write a TLDR of ≤100 words.",
    "report": "Write a structured report: Overview, Key Points, Implications.",
}


async def run(ctx: RouteContext) -> RouteResult:
    space_id = ctx.input.get("space_id")
    if not space_id:
        return RouteResult(text="space_id is required.", ok=False, error="missing_input")

    url: str = ctx.input.get("url", "(no URL provided)")
    title: str = ctx.input.get("title", "Untitled")
    transcript: str = ctx.input.get("transcript", "")
    style: str = ctx.input.get("style", "key_takeaways")

    if not transcript:
        return RouteResult(
            text="No transcript provided. Transcript fetch is not yet implemented.",
            ok=False,
            error="no_transcript",
        )

    style_instruction = _STYLE_INSTRUCTIONS.get(style, _STYLE_INSTRUCTIONS["key_takeaways"])
    prompt = _YOUTUBE_PROMPT_TEMPLATE.format(
        space_id=space_id,
        title=title,
        url=url,
        transcript=transcript[:6000],
        style_instruction=style_instruction,
    )

    try:
        text = await ctx.call_llm(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.exception("spaces-youtube-summary: LLM call failed")
        return RouteResult(text=f"YouTube summary failed: {exc}", ok=False, error="llm_error")

    # Optionally append to knowledge-base.md
    try:
        space_dir = ctx.layout.entity_dir(ctx.user_id, "spaces", space_id)
        kb_path = space_dir / "knowledge-base.md"
        with kb_path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n\n## Video: {title}\n\n{text}\n")
    except Exception:  # noqa: BLE001
        logger.warning("spaces-youtube-summary: could not append to knowledge-base.md")

    return RouteResult(
        text=text,
        metadata={"space_id": space_id, "url": url, "style": style},
    )
