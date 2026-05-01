---
name: improve-code
description: Improves code quality and style against project rules through a gated sequence — first map how the file is used (zoom-out), then plan the changes through a grilling session (grill-me), then implement. Maintains a markdown record of the user's durable coding preferences. Use when the user wants code improvements, style fixes, architectural discussion, or to understand how a file fits the system.
disable-model-invocation: true
---

# Improve code

Complete the steps below in order. Each step ends with a hard checkpoint — wait for the user before continuing.

## Step 1 — Map (how is this file used?)

Load and follow [zoom-out](../zoom-out/SKILL.md): go up a layer of abstraction and map the file in its surroundings. Borrow architecture vocabulary from [improve-codebase-architecture](../improve-codebase-architecture/SKILL.md) ([LANGUAGE.md](../improve-codebase-architecture/LANGUAGE.md)) — module, interface, depth, seam, adapter, leverage, locality.

Produce a short summary (aim for ~6 lines):

- **Purpose** — one sentence.
- **Callers / callees** — who uses it, what it depends on. Cite files.
- **Domain vocabulary** — terms from `CONTEXT.md` that apply (flag missing/fuzzy ones).
- **Notable observations** — rule violations, design smells, anything worth flagging. Don't propose fixes yet.

### When there are no (or very few) callers

"Zero callers" is **not** a valid stopping point. Dig until you can describe the file's *intended* role.

Investigate intent: repo-level docs (`README.md`, `DESIGN.md`, `FUTURE.md`, `plans/`, `docs/`, `docs/adr/`), sibling files, `__init__.py` / re-exports, docstrings and comments, `git log -- <file>`, any `references/` ports (read the source repo's callers), and dependencies in `pyproject.toml` / `package.json`.

Add to the summary:

- **Intended use** — best guess at *"what is this file supposed to do, and who is supposed to call it?"*. Cite evidence. Mark confidence: `clear` / `inferred` / `speculative`.

Then present numbered options with a recommended default, e.g.:

1. Wire up a real caller now (name the target site).
2. Keep and improve in line with the inferred intent.
3. Mark deprecated / park (move to `references/`, add a deprecation note).
4. Delete as dead code.

**Stop and wait** for the user to pick one (or propose another).

### Default checkpoint (callers exist)

**Checkpoint:** present the summary, then ask _"Does that match your mental model? Anything to add or correct before we plan changes?"_ **Stop and wait.**

## Step 2 — Plan (grill-me)

Load and follow [grill-me](../grill-me/SKILL.md). The phases below are sequential — don't collapse them.

### 2a. Grill on agent observations

Turn Step 1's observations into a numbered list of candidate changes, then walk the decision tree:

- Ask **one focused question at a time**, each with your recommended answer.
- Resolve dependencies one-by-one.
- If a question can be answered by reading code, read first instead of asking.

### 2b. Invite user-driven changes

Once the agent-driven branches are settled, **explicitly ask** whether the user wants other specific changes that didn't come up in Step 1, e.g.:

> _"Before we lock the plan: any other specific changes you want made to this file that I haven't flagged? (rename X, change behaviour Y, drop Z, add a test for…)"_

For each item, grill the same way as in 2a — one question at a time, recommended answer, resolve dependencies, read code instead of asking when you can. Add the item (or its rejection, with reason) to the running plan. Loop until the user has nothing more to add. Don't skip this prompt even if the agent-side plan looks complete.

### 2c. Rules and code quality pass

Now (not at the start) walk the [Code quality checklist](./CODE-QUALITY-CHECKLIST.md) against the file — `AGENTS.md`, then `simplify`, then `CODING-PREFERENCES.md`. `AGENTS.md` takes precedence over `CODING-PREFERENCES.md`; flag conflicts rather than silently dropping either.

Add any violations or quality fixes to the plan as additional items. Grill any non-trivial ones the same way as 2a / 2b.

### 2d. Final approval

**Checkpoint:** restate the agreed plan as a short numbered list, clearly separating items from agent observations (2a), user requests (2b), and rules / quality (2c). Ask _"Apply this?"_ **Stop and wait** for explicit approval before editing any source file.

## Step 3 — Implement

Apply the approved plan using the [Code quality checklist](./CODE-QUALITY-CHECKLIST.md).

## Step 4 — Verify

Run existing tests and lint (e.g. `pytest`, `ruff check` — pick what the project actually uses). Fix failures before surfacing the result.

## Step 5 — Summarise

One short paragraph: what changed, which rule / preference drove it, any open questions or follow-ups deferred from Step 2.

## Step 6 — Feedback

Explicitly invite feedback on the applied changes, e.g.:

> _"Anything about how I handled this you'd want done differently next time? (style, naming, scope, how we grilled, when I checkpointed…)"_

Capture each piece of feedback verbatim (or in tight paraphrase) and tag whether it's:

- **One-off** — this PR only; don't promote.
- **Durable** — should change default behaviour going forward; carry into Step 7.
- **Conflict** — disagrees with `AGENTS.md` or an existing `CODING-PREFERENCES.md` bullet; surface the conflict explicitly and ask the user which wins.

If there is no feedback, say so and skip Step 7.

## Step 7 — Preferences

Fold any **durable** items from Step 6 (and any preferences that emerged during the Step 2 grilling) into `CODING-PREFERENCES.md` — follow [CODING-PREFERENCES-FORMAT.md](./CODING-PREFERENCES-FORMAT.md) for path, when-to-patch rules, and section format. Don't promote one-off items.

## Skipping steps

Only skip a step when the user **explicitly says so** in the same turn (e.g. _"skip the map, just fix the docstrings"_). Note the skip in your response so it's traceable.

For trivial edits (one-line typo, single-character fix) the Map and Plan steps may collapse to one or two sentences each — but they still happen and still end with a checkpoint.
