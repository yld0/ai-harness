# CODING-PREFERENCES.md format

**Path:** repository root `CODING-PREFERENCES.md` (create lazily on first durable preference).

**Purpose:** running log of the user's **general** coding quality and style preferences — not per-PR notes.

## When to patch

- The user states a preference they want remembered (habit, default, line in the sand).
- A repeated pattern emerges in conversation ("always prefer X") and they confirm.

## When not to patch

- One-off decisions for a single ticket.
- Duplicates of what is already in `AGENTS.md` (link to the rule instead).

## Format (keep short)

Stable sections, append bullets:

```markdown
# Coding preferences

## Style

- …

## Architecture / design

- …

## Process

- …
```

Each bullet: imperative, specific, dated only if the user cares about history (optional `YYYY-MM:` prefix).

## Patch discipline

- Merge near-related bullets; avoid sprawling essays.
- After updating, tell the user what section changed in one sentence.
