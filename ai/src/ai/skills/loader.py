"""Read SKILL.md from disk with containment and size checks."""

from __future__ import annotations

from pathlib import Path

from ai.skills.safety import (
    MAX_SKILL_FILE_BYTES,
    is_under_any_root,
    scan_injection_hits,
    should_reject_on_injection,
)


class SkillLoadError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def read_skill_file(path: Path, *, allowed_roots: list[Path], max_bytes: int = MAX_SKILL_FILE_BYTES) -> str:
    if not is_under_any_root(path, allowed_roots):
        raise SkillLoadError("path_not_allowed", f"Skill path is outside allowed roots: {path}")
    try:
        st = path.stat()
    except OSError as exc:
        raise SkillLoadError("read_error", str(exc)) from exc
    if st.st_size > max_bytes:
        raise SkillLoadError("oversize", f"SKILL.md exceeds {max_bytes} bytes")
    text = path.read_text(encoding="utf-8", errors="strict")
    hits = scan_injection_hits(text)
    if should_reject_on_injection(hits):
        raise SkillLoadError("injection_suspect", f"Content failed safety scan: {', '.join(hits)}")
    return text
