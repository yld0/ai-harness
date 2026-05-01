"""Writers for daily notes, entity facts, and synthesized summaries."""

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ai.memory.decay import decay_score, include_in_summary, update_decay_state
from ai.memory.para import MemoryEntityKind, ParaMemoryLayout
from ai.memory.schemas import FactStatus, MemoryFact, Validity
from ai.memory.threat_scan import safe_memory_text


class MemoryWriter:
    def __init__(self, layout: ParaMemoryLayout | None = None) -> None:
        self.layout = layout or ParaMemoryLayout()

    def append_daily_note(
        self,
        user_id: str,
        text: str,
        *,
        day: date | None = None,
        now: datetime | None = None,
    ) -> Path:
        day = day or date.today()
        now = now or datetime.now(timezone.utc)
        path = self.layout.daily_note_path(user_id, day.isoformat())
        path.parent.mkdir(parents=True, exist_ok=True)
        safe = safe_memory_text(text, source="daily_note").strip()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n- {now.isoformat()}: {safe}\n")
        return path

    def write_fact(
        self,
        user_id: str,
        *,
        kind: MemoryEntityKind,
        entity_id: str,
        fact: MemoryFact,
    ) -> Path:
        safe_memory_text(fact.fact, source=fact.id)
        entity_dir = self.ensure_entity_layout(user_id, kind=kind, entity_id=entity_id)
        path = entity_dir / "items.yaml"
        facts = self.read_facts_path(path)
        facts.append(fact)
        self.write_facts_path(path, facts)
        return path

    def ensure_entity_layout(self, user_id: str, *, kind: MemoryEntityKind, entity_id: str) -> Path:
        entity_dir = self.layout.entity_dir(user_id, kind, entity_id)
        entity_dir.mkdir(parents=True, exist_ok=True)
        for file_name in self._entity_files(kind):
            path = entity_dir / file_name
            if not path.exists():
                path.write_text(self._initial_content(file_name, entity_id), encoding="utf-8")
        return entity_dir

    def synthesize_summary(
        self,
        user_id: str,
        *,
        kind: MemoryEntityKind,
        entity_id: str,
        today: date | None = None,
    ) -> Path:
        today = today or date.today()
        entity_dir = self.ensure_entity_layout(user_id, kind=kind, entity_id=entity_id)
        facts_path = entity_dir / "items.yaml"
        facts = [update_decay_state(fact, today=today) for fact in self.read_facts_path(facts_path)]
        self.write_facts_path(facts_path, facts)

        current: list[str] = []
        fading: list[str] = []
        historical: list[str] = []
        for fact in facts:
            if not include_in_summary(fact, today=today):
                continue
            if fact.status == FactStatus.HISTORICAL:
                historical.append(self._summary_line(fact, today=today))
            elif fact.validity == Validity.POINT_IN_TIME and decay_score(fact, today=today) < 0.5:
                fading.append(self._summary_line(fact, today=today))
            elif fact.status == FactStatus.ACTIVE:
                current.append(self._summary_line(fact, today=today))

        content = [
            f"# {entity_id} — Summary",
            f"Updated: {today.isoformat()}",
            "",
            "## Current",
            *(current or ["- None"]),
            "",
            "## Fading",
            *(fading or ["- None"]),
            "",
            "## Historical",
            *(historical or ["- None"]),
            "",
        ]
        path = entity_dir / "summary.md"
        path.write_text("\n".join(content), encoding="utf-8")
        return path

    @staticmethod
    def read_facts_path(path: Path) -> list[MemoryFact]:
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            return []
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if not isinstance(raw, list):
            raise ValueError(f"expected list in {path}")
        return [MemoryFact.model_validate(item) for item in raw]

    @staticmethod
    def write_facts_path(path: Path, facts: list[MemoryFact]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [fact.to_yaml_dict() for fact in facts]
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    @staticmethod
    def _entity_files(kind: MemoryEntityKind) -> tuple[str, ...]:
        base = ("summary.md", "items.yaml")
        if kind == "tickers":
            return (*base, "thesis.md", "valuation.yaml", "consensus.yaml")
        if kind == "spaces":
            return (*base, "sources.yaml", "knowledge-base.md")
        return base

    @staticmethod
    def _initial_content(file_name: str, entity_id: str) -> str:
        if file_name.endswith(".md"):
            return f"# {entity_id}\n"
        return "[]\n"

    @staticmethod
    def _summary_line(fact: MemoryFact, *, today: date) -> str:
        suffix = f" [confidence: {fact.confidence.value}]"
        if fact.validity == Validity.EXPIRES and fact.expires:
            suffix += f" [expires: {fact.expires.isoformat()}]"
        if fact.validity == Validity.POINT_IN_TIME:
            suffix += f" [recorded: {fact.recorded_at.isoformat()}, decay: {decay_score(fact, today=today):.2f}]"
        return f"- {fact.fact}{suffix}"
