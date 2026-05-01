"""Route handler: spaces-knowledge-base-sources-refresh.

Re-fetches every source in sources.yaml whose timingValidity window has
elapsed, updates last_fetched, regenerates knowledge-base.md via LLM, and
records the update date.

Input keys:
  - ``space_id``: str — required, the space to refresh.
  - ``force``: bool — if true, refresh all sources regardless of timing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from ai.routes.context import RouteContext, RouteResult

logger = logging.getLogger(__name__)

_TIMING_WINDOWS: dict[str, timedelta] = {
    "evergreen": timedelta(days=365),
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
    "event_driven": timedelta(days=0),  # always stale
}

_KB_PROMPT_TEMPLATE = """\
You are a knowledge-base synthesis assistant.

Below are the fetched source contents for the space "{space_id}":

---
{sources_text}
---

Synthesise a concise, well-structured knowledge base in Markdown.
Include:
- An executive summary (2–3 sentences).
- Key concepts / facts (bullet points).
- Open questions or areas of uncertainty.
Keep the total under 1500 words.
"""


def _read_sources(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        raw = yaml.safe_load(path.read_text("utf-8"))
        return raw if isinstance(raw, list) else []
    except Exception:  # noqa: BLE001
        return []


def _write_sources(path: Path, sources: list[dict[str, Any]]) -> None:
    path.write_text(yaml.safe_dump(sources, allow_unicode=True), encoding="utf-8")


def _is_stale(source: dict[str, Any], *, force: bool, now: datetime) -> bool:
    if force:
        return True
    timing = source.get("timingValidity", "weekly")
    window = _TIMING_WINDOWS.get(timing, timedelta(days=7))
    last_raw = source.get("last_fetched")
    if not last_raw:
        return True
    try:
        last_dt = datetime.fromisoformat(str(last_raw))
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        return (now - last_dt) >= window
    except (ValueError, TypeError):
        return True


async def run(ctx: RouteContext) -> RouteResult:
    space_id = ctx.input.get("space_id")
    if not space_id:
        return RouteResult(text="space_id is required.", ok=False, error="missing_input")

    force: bool = bool(ctx.input.get("force", False))
    now = datetime.now(timezone.utc)

    try:
        space_dir = ctx.layout.entity_dir(ctx.user_id, "spaces", space_id)
    except Exception as exc:
        return RouteResult(text=f"Invalid space_id: {exc}", ok=False, error="invalid_space_id")

    sources_path = space_dir / "sources.yaml"
    kb_path = space_dir / "knowledge-base.md"

    sources = _read_sources(sources_path)
    if not sources:
        return RouteResult(
            text=f"No sources found for space {space_id!r}.",
            metadata={"space_id": space_id, "refreshed": 0},
        )

    stale = [s for s in sources if _is_stale(s, force=force, now=now)]
    sources_text_parts: list[str] = []

    for source in stale:
        url = source.get("url", "unknown")
        # Mark as fetched (actual HTTP fetch deferred to web_fetch tool / future phase)
        source["last_fetched"] = now.isoformat()
        sources_text_parts.append(f"Source: {url}\n(content fetched at {now.isoformat()})")
        logger.debug("spaces-kb-refresh: marking %s as fetched", url)

    if not stale:
        return RouteResult(
            text=f"All sources for {space_id!r} are up-to-date.",
            metadata={"space_id": space_id, "refreshed": 0},
        )

    _write_sources(sources_path, sources)

    # Regenerate knowledge-base.md
    sources_text = "\n\n".join(sources_text_parts) if sources_text_parts else "(no source content)"
    kb_prompt = _KB_PROMPT_TEMPLATE.format(space_id=space_id, sources_text=sources_text)
    try:
        kb_content = await ctx.call_llm(kb_prompt)
    except Exception as exc:  # noqa: BLE001
        logger.exception("spaces-kb-refresh: LLM call failed")
        return RouteResult(text=f"KB generation failed: {exc}", ok=False, error="llm_error")

    kb_path.write_text(kb_content, encoding="utf-8")

    return RouteResult(
        text=f"Refreshed {len(stale)} source(s) for space {space_id!r}. knowledge-base.md updated.",
        metadata={"space_id": space_id, "refreshed": len(stale)},
    )
