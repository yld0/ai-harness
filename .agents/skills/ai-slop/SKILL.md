---
name: ai-slop
description: Strip AI-style noise from code — redundant comments, abnormal defensive checks, Any-casts, local style drift. Two scopes ask if unclear (current file/selection vs diff vs main); prefer improve-codebase-architecture when structure is the problem. Use when removing AI slop, cleaning a branch/PR, or sanitizing before review.
disable-model-invocation: true
---

# Remove AI code slop

## Decision order

1. **Is the problem structural?** Tangled seams, unclear boundaries, shallow modules with sprawling interfaces — **stop**. Point the user at [improve-codebase-architecture](../improve-codebase-architecture/SKILL.md). Stripping slop on top of bad structure buries the real issue. Resume slop removal only after architectural direction exists.

2. **Pick scope.** If the user did not specify, **ask once**:
   - **Current file / selection only** — boundary is the open file(s) or pasted selection. Do not widen to the whole repo unless needed to verify types or callers.
   - **Diff vs trunk** — use `git diff main...HEAD` when `main` exists; otherwise the repository default branch (`master`, `develop`, etc.). Limit edits to what the branch touched (and immediate context so hunks stay coherent).

   Record the chosen scope and stick to it until the user changes it.

3. **Apply the pass** (below).

---

## Improve code (shared)

- Align with project rules and the file’s existing style.
- Briefly explain how affected code fits the system (callers, callees, vocabulary) **before** editing when it informs what counts as slop vs intentional pattern.
- For **current file**, agree the edit list **before** implementing when removals are ambiguous.
- For **diff vs trunk**, skim per-file deltas and plan the minimal slop-stripping pass; do not refactor unrelated legacy code outside the branch.
- Record stable preferences in [`CODING-PREFERENCES.md`](../../../CODING-PREFERENCES.md).
- **Slop targets** — comments a human wouldn’t add or that fight the surrounding file; `try`/except (or overly broad guards) that are abnormal on trusted paths; `Any`/casts used to bypass the type checker; verbosity or patterns that drift from neighbouring code.

---

## Project rules first

Read workspace rules (`AGENTS.md`, `.cursor/rules/` if present). `AGENTS.md` overrides [`CODING-PREFERENCES.md`](../../../CODING-PREFERENCES.md); say so if they conflict.

Call out violations; fix within scope where slop-removal aligns with rules.

---

## Mechanical pass (within scope)

**Goal:** Remove AI-introduced cruft **without behavioural change** — no feature edits, no new abstractions, no drive-by redesign outside scope.

Applicable items (same bar as mechanical simplify):

1. **Formatting** — fix only if inconsistent with the file or obviously introduced with the cruft (indentation, stray blank lines, trailing whitespace).
2. **Naming** — only when a slop-introduced name is clearly wrong locally; **do not** rename public exports unless the user confirms.
3. **Dead code** — unused imports, unreachable blocks, commented-out experiments tied to branch work.
4. **Obvious simplifications** — redundant conditions, clumsy idioms (`if x is True`, etc.) when they landed with slop.
5. **Imports** — sort/dedupe where the branch touched them; **no imports inside functions** unless project rules require an exception (e.g. cycles).
6. **Docstrings** — padded delimiters (`""" text. """`) per project rules where you touch them; drop docstrings that only restate the signature.

Prefer proper types over `Any`; do not widen `try`/except to swallow errors silently.

Ensure tests still pass afterward (scoped run when the repo is large).

### Constraints

- Match each file’s **existing** style — do not impose a different style from elsewhere in the repo.
- **Diff scope:** constrain changes to branch-introduced or branch-touched surfaces; preserve branch intent; flag risky “fixes” instead of slipping them in.
- **Current file:** same no-behaviour-change rule; confirm before API-visible renames.

---

## Output

End with **1–3 sentences**: what categories of slop were removed and rough site counts (per file when diff-scoped).
