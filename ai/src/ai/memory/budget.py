"""Memory prompt budgeting and fencing."""

from dataclasses import dataclass

from ai.memory.threat_scan import safe_memory_text

DEFAULT_MEMORY_BUDGET_CHARS = 25_000


@dataclass(frozen=True)
class MemoryBlock:
    content: str
    used_chars: int
    truncated: bool = False


def build_memory_context(
    *,
    user_memory: str = "",
    user_profile: str = "",
    entity_summaries: list[tuple[str, str]] | None = None,
    budget_chars: int = DEFAULT_MEMORY_BUDGET_CHARS,
) -> MemoryBlock:
    sections: list[tuple[str, str]] = [
        ("USER.md", user_profile.strip()),
        ("MEMORY.md", user_memory.strip()),
    ]
    sections.extend(entity_summaries or [])

    body_parts: list[str] = ["[System note: The following is recalled memory context, NOT new user input.]"]
    used = len("\n".join(body_parts))
    truncated = False

    for title, raw in sections:
        if not raw:
            continue
        text = safe_memory_text(raw, source=title)
        rendered = f"## {title}\n{text}"
        separator = "\n\n" if body_parts else ""
        remaining = budget_chars - used - len(separator)
        if remaining <= 0:
            truncated = True
            break
        if len(rendered) > remaining:
            body_parts.append(separator + rendered[: max(0, remaining - 16)].rstrip() + "\n[truncated]")
            truncated = True
            used = budget_chars
            break
        body_parts.append(separator + rendered)
        used += len(separator) + len(rendered)

    content = "".join(body_parts)
    return MemoryBlock(
        content=f"<memory-context>\n{content}\n</memory-context>",
        used_chars=len(content),
        truncated=truncated,
    )
