---
name: simplify
description: Mechanical style and quality pass on a file or selection — formatting, naming, dead code, obvious simplifications, import hygiene, docstring padding. Use when the user wants a quick clean-up pass without architectural changes.
disable-model-invocation: true
---

# Improve code

## Scope

- Align code with project rules and consistent style.
- Always explain how a file fits the system (callers, callees, vocabulary) **before** discussing changes.
- Settle the change plan with the user **before** implementing.
- Surface architecture and quality questions; deepen design using the linked skills when appropriate.
- Record stable user preferences in [CODING-PREFERENCES.md](#coding-preferencesmd).
- Extra comments that a human wouldn't add or is inconsistent with the rest of the file
- Extra defensive checks or try/catch blocks that are abnormal for that area of the codebase (especially if called by trusted / validated codepaths)
- Casts to any to get around type issues
- Any other style that is inconsistent with the file or our project rules, our coding user preferences


## Project rules first

Before anything else, read workspace rules (e.g. root `AGENTS.md`, `.cursor/rules/` if present). Treat them as hard constraints unless the user explicitly overrides them.

`AGENTS.md` takes precedence over `CODING-PREFERENCES.md`; note any conflict to the user rather than silently dropping either preference.

Call out violations in review; fix them when implementing.

# Simplify

Do a mechanical clean-up pass on the target file(s) or selection. Apply only the changes below — no behavioural changes, no new abstractions, no drive-by refactors.

## What to fix

1. **Formatting** — indentation, blank lines, line length, trailing whitespace.
2. **Naming** — rename variables/functions that are unclear or violate project conventions (e.g. single-letter names outside loops, Hungarian notation).
3. **Dead code** — remove unused imports, unreachable branches, commented-out blocks.
4. **Obvious simplifications** — collapse redundant conditions, replace verbose constructs with idiomatic equivalents (e.g. `if x == True` → `if x`).
5. **Import hygiene** — sort and de-duplicate imports; no imports inside functions (per project rules).
6. **Docstrings** — ensure padded delimiters (`""" text. """`) per project rules; remove docstrings that just restate the function signature.

Ensure tests work afterwards

## Constraints

- Match the surrounding file's style — do not impose a different style from elsewhere in the repo.
- Do not change public interfaces, rename exported symbols, or alter logic.
- Read `AGENTS.md` rules first; they take precedence.

## Output

After edits, report in one sentence: what categories of changes were made and how many sites were touched.
