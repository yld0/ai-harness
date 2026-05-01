"""Local memory search with optional qmd integration."""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ai.memory.para import ParaMemoryLayout


@dataclass(frozen=True)
class MemorySearchResult:
    path: str
    score: float
    snippet: str


class MemorySearch:
    def __init__(self, layout: ParaMemoryLayout | None = None) -> None:
        self.layout = layout or ParaMemoryLayout()

    def local_search(self, user_id: str, query: str, *, limit: int = 10) -> list[MemorySearchResult]:
        root = self.layout.user_root(user_id)
        terms = {term.lower() for term in query.split() if term.strip()}
        if not terms or not root.exists():
            return []
        results: list[MemorySearchResult] = []
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".md", ".yaml", ".yml"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            lowered = text.lower()
            hits = sum(lowered.count(term) for term in terms)
            if hits <= 0:
                continue
            snippet = self._snippet(text, terms)
            results.append(
                MemorySearchResult(
                    path=str(path.relative_to(root)),
                    score=float(hits),
                    snippet=snippet,
                )
            )
        return sorted(results, key=lambda item: item.score, reverse=True)[:limit]

    def qmd_query(self, user_id: str, query: str, *, limit: int = 10) -> list[MemorySearchResult]:
        if shutil.which("qmd") is None:
            return self.local_search(user_id, query, limit=limit)
        root = self.layout.user_root(user_id)
        completed = subprocess.run(
            ["qmd", "query", query, str(root)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if completed.returncode != 0:
            return self.local_search(user_id, query, limit=limit)
        lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        return [MemorySearchResult(path=f"qmd:{idx}", score=float(limit - idx), snippet=line) for idx, line in enumerate(lines[:limit])]

    @staticmethod
    def _snippet(text: str, terms: set[str]) -> str:
        lower = text.lower()
        index = min((lower.find(term) for term in terms if term in lower), default=0)
        start = max(0, index - 60)
        end = min(len(text), index + 160)
        return text[start:end].replace("\n", " ").strip()
