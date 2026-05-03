"""Structured prompt for single-shot memory consolidation (dream)."""

from __future__ import annotations


def build_consolidation_prompt(
    *,
    memory_root_display: str,
    memory_index_text: str,
    daily_notes_text: str,
    entity_summaries_text: str,
    extra: str = "",
) -> str:
    """Build the user message body instructing the model how to consolidate PARA memory."""
    extra_block = f"\n\n## Additional context\n\n{extra.strip()}" if extra.strip() else ""
    return f"""# Dream: Memory Consolidation

You are performing a dream: a reflective pass over the user's PARA memory files. Synthesize recent signal into durable, well-organized memories so future sessions orient quickly.

Memory root (filesystem): `{memory_root_display}`

---

## Current MEMORY.md (index)

```markdown
{memory_index_text.strip() or "(empty)"}
```

## Recent daily notes (append-only signal)

```markdown
{daily_notes_text.strip() or "(none provided)"}
```

## Entity summaries (existing topic files under life/<kind>/<id>/summary.md)

```markdown
{entity_summaries_text.strip() or "(none found)"}
```

---

## Phase 1: Orient

- Treat MEMORY.md as the **index**, not long-form storage.
- Prefer merging into existing entity summaries rather than inventing duplicates.

## Phase 2: Gather signal

Prioritize facts that will still matter after weeks: stable preferences, project facts, corrections to prior beliefs, repeatable procedures.

## Phase 3: Consolidate

- Convert vague time references into ISO dates where you can infer them safely.
- Remove or supersede contradictions.

## Phase 4: Prune index

MEMORY.md stays compact: short bullet or link lines, under ~25KB preferred.

---

## Required output format (machine-parseable)

Emit **only** the following tagged blocks (no prose outside tags). Replace placeholders with finalized markdown file bodies.

```
<<MEMORY_INDEX>>
...complete replacement body for MEMORY.md...
<<END>>
```

For **each** entity summary you revise or create, emit one block (`kind` is one of: tickers, sectors, spaces, watchlists, people, macros; `entity_id` matches directory name):

```
<<ENTITY kind entity_id>>
...complete replacement body for that entity's summary.md...
<<END>>
```

If MEMORY.md needs no changes, repeat its current trimmed content unchanged in the MEMORY_INDEX block.

End with nothing after the closing `<<END>>` tags.{extra_block}
"""
