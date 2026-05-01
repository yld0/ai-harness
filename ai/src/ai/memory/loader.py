"""Hot memory snapshot loading with Hermes-style session freezing."""

from dataclasses import dataclass
from pathlib import Path

from ai.memory.budget import MemoryBlock, build_memory_context
from ai.memory.para import ParaMemoryLayout
from ai.memory.schemas import HotMemorySnapshot


@dataclass(frozen=True)
class MemorySessionKey:
    user_id: str
    session_id: str


class MemoryLoader:
    def __init__(self, layout: ParaMemoryLayout | None = None, *, budget_chars: int = 25_000) -> None:
        self.layout = layout or ParaMemoryLayout()
        self.budget_chars = budget_chars
        self._cache: dict[MemorySessionKey, HotMemorySnapshot] = {}

    def load_hot_snapshot(
        self,
        *,
        user_id: str,
        session_id: str,
        first_message: str = "",
        rebuild: bool = False,
    ) -> HotMemorySnapshot:
        key = MemorySessionKey(user_id=user_id, session_id=session_id)
        if not rebuild and key in self._cache:
            return self._cache[key]

        root = self.layout.ensure_user_layout(user_id)
        user_profile = self._read(root / "USER.md")
        user_memory = self._read(root / "MEMORY.md")
        entity_summaries = self._entity_summaries(root, first_message)
        block = build_memory_context(
            user_memory=user_memory,
            user_profile=user_profile,
            entity_summaries=entity_summaries,
            budget_chars=self.budget_chars,
        )
        snapshot = HotMemorySnapshot(
            user_id=user_id,
            session_id=session_id,
            content=block.content,
            user_profile=user_profile,
            metadata={
                "used_chars": block.used_chars,
                "truncated": block.truncated,
                "entity_summaries": [name for name, _ in entity_summaries],
            },
        )
        self._cache[key] = snapshot
        return snapshot

    def invalidate(self, *, user_id: str, session_id: str) -> None:
        self._cache.pop(MemorySessionKey(user_id=user_id, session_id=session_id), None)

    @staticmethod
    def _read(path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="replace").strip()

    def _entity_summaries(self, root: Path, first_message: str) -> list[tuple[str, str]]:
        mentioned = self._mentioned_tokens(first_message)
        summaries: list[tuple[str, str]] = []
        life = root / "life"
        for kind in ("tickers", "spaces", "watchlists", "people", "macros", "sectors"):
            base = life / kind
            if not base.is_dir():
                continue
            for entity_dir in sorted(base.iterdir()):
                if not entity_dir.is_dir():
                    continue
                if entity_dir.name.lower() not in mentioned:
                    continue
                summary = self._read(entity_dir / "summary.md")
                if summary:
                    summaries.append((f"{kind}/{entity_dir.name}/summary.md", summary))
        return summaries

    @staticmethod
    def _mentioned_tokens(text: str) -> set[str]:
        normalized = text.lower().replace("/", " ")
        return {token.strip(".,:;()[]{}") for token in normalized.split() if token}
