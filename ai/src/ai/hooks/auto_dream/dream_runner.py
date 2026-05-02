"""Consolidates PARA memory via one LLM pass and guarded file writes."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from ai.memory.para import MemoryEntityKind, ParaMemoryLayout, MemoryPathError
from ai.providers.one_shot import LLMCaller, one_shot_caller
from ai.hooks.auto_dream.consolidation_prompt import build_consolidation_prompt
from ai.telemetry.posthog import capture_event

logger = logging.getLogger(__name__)

_ENTITY_KINDS: tuple[MemoryEntityKind, ...] = (
    "tickers",
    "sectors",
    "spaces",
    "watchlists",
    "people",
    "macros",
)

_MEMORY_BLOCK_RE = re.compile(r"<<MEMORY_INDEX>>\s*(.*?)\s*<<END>>", re.DOTALL)
_ENTITY_BLOCK_RE = re.compile(
    r"<<ENTITY\s+(tickers|sectors|spaces|watchlists|people|macros)\s+([A-Za-z0-9._-]+)>>" r"\s*(.*?)\s*<<END>>",
    re.DOTALL,
)


@dataclass
class DreamResult:
    """Outcome of a consolidation run."""

    ok: bool
    files_written: list[str] = field(default_factory=list)
    detail: str = ""
    skipped_parse: bool = False


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def gather_memory_index(layout: ParaMemoryLayout, user_id: str) -> str:
    """Load ``MEMORY.md`` from the user root."""
    return _read_text(layout.guarded_user_path(user_id, "MEMORY.md"))


def gather_recent_daily_notes(layout: ParaMemoryLayout, user_id: str, recent_days: int) -> str:
    """Concatenate up to *recent_days* calendar daily notes ending at today."""
    if recent_days <= 0:
        return ""
    mem = layout.guarded_user_path(user_id, "memory")
    if not mem.is_dir():
        return ""
    parts: list[str] = []
    today = date.today()
    for i in range(recent_days):
        day = (today - timedelta(days=i)).isoformat()
        path = mem / f"{day}.md"
        if path.is_file():
            body = _read_text(path).strip()
            parts.append(f"### {day}.md\n\n{body}\n")
    return "\n".join(parts)


def gather_entity_summaries(layout: ParaMemoryLayout, user_id: str) -> str:
    """Concatenate ``summary.md`` bodies for entities under ``life/*/``."""
    parts: list[str] = []
    for kind in _ENTITY_KINDS:
        kind_dir = layout.guarded_user_path(user_id, "life", kind)
        if not kind_dir.is_dir():
            continue
        for ent in sorted(kind_dir.iterdir(), key=lambda p: p.name):
            if not ent.is_dir():
                continue
            sm = layout.guarded_user_path(user_id, "life", kind, ent.name, "summary.md")
            if sm.is_file():
                body = _read_text(sm).strip()
                parts.append(f"### {kind}/{ent.name}/summary.md\n\n{body}\n")
    return "\n".join(parts)


def parse_dream_blocks(raw: str) -> tuple[str | None, list[tuple[str, str, str]]]:
    """Return ``(memory_index_body, [(kind, entity_id, summary_body), ...])``."""
    mm = _MEMORY_BLOCK_RE.search(raw)
    memory_index = mm.group(1).strip() if mm else None
    entities: list[tuple[str, str, str]] = []
    for m in _ENTITY_BLOCK_RE.finditer(raw):
        kind_raw, eid_raw, body = m.group(1), m.group(2), m.group(3).strip()
        entities.append((kind_raw, eid_raw, body))
    return memory_index, entities


class DreamRunner:
    """Loads memory files, invokes the LLM once, parses tagged output, writes back."""

    def __init__(
        self,
        layout: ParaMemoryLayout | None = None,
        call_llm: LLMCaller | None = None,
        *,
        system_message: str | None = None,
    ) -> None:
        self._layout = layout
        self._call_llm = call_llm
        self._system_message = system_message

    def _get_layout(self) -> ParaMemoryLayout:
        if self._layout is not None:
            return self._layout
        return ParaMemoryLayout()

    def _get_llm(self, model_override: str | None) -> LLMCaller:
        if self._call_llm is not None:
            return self._call_llm
        return one_shot_caller(model_override=model_override, system_message=self._system_message)

    async def run(
        self,
        user_id: str,
        *,
        recent_daily_notes: int,
        dream_model_override: str | None = None,
        extra_prompt: str = "",
    ) -> DreamResult:
        """Consolidate memories for *user_id*."""
        layout = self._get_layout()
        root_disp = str(layout.memory_root.resolve())

        mem_index = gather_memory_index(layout, user_id).strip()
        daily_blob = gather_recent_daily_notes(layout, user_id, recent_daily_notes).strip()
        entities_blob = gather_entity_summaries(layout, user_id).strip()

        user_prompt = build_consolidation_prompt(
            memory_root_display=root_disp,
            memory_index_text=mem_index or "(empty)",
            daily_notes_text=daily_blob or "(none)",
            entity_summaries_text=entities_blob or "(none)",
            extra=extra_prompt,
        )
        caller = self._get_llm((dream_model_override or "").strip() or None)
        try:
            raw = await caller(user_prompt)
        except Exception as exc:
            capture_event(user_id, "auto_dream_failed", {"reason": type(exc).__name__})
            logger.exception("dream LLM call failed")
            return DreamResult(ok=False, detail=str(exc))

        parsed_index, entities = parse_dream_blocks(raw)
        if parsed_index is None:
            capture_event(user_id, "auto_dream_failed", {"reason": "parse_memory_index"})
            logger.warning("dream output missing MEMORY_INDEX block")
            return DreamResult(ok=False, detail="missing_MEMORY_INDEX_block", skipped_parse=True)

        written: list[str] = []

        try:
            mi_path = layout.guarded_user_path(user_id, "MEMORY.md")
        except MemoryPathError as exc:
            capture_event(user_id, "auto_dream_failed", {"reason": type(exc).__name__})
            return DreamResult(ok=False, detail=str(exc))

        mi_path.parent.mkdir(parents=True, exist_ok=True)
        mi_path.write_text(parsed_index.strip() + "\n", encoding="utf-8")
        written.append(str(mi_path))

        kinds_set = set(_ENTITY_KINDS)
        for kind_s, entity_id, body in entities:
            if kind_s not in kinds_set or not entity_id.strip():
                continue
            try:
                out = layout.guarded_user_path(user_id, "life", kind_s, entity_id, "summary.md")
            except MemoryPathError as exc:
                logger.warning("skip entity block %s/%s: %s", kind_s, entity_id, exc)
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(body.strip() + "\n", encoding="utf-8")
            written.append(str(out))

        capture_event(
            user_id,
            "auto_dream_completed",
            {"files_written": len(written), "entities_updated": len(entities)},
        )
        return DreamResult(ok=True, files_written=written, detail="completed")
