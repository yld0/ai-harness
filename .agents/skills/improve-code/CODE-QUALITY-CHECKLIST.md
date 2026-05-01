# Code quality checklist

Used in **2c** (planning) and **Step 3** (implementing) of [SKILL.md](./SKILL.md). The checklist is exactly these three sources, in priority order:

1. **[AGENTS.md](../../../AGENTS.md)** — workspace rules (root `AGENTS.md` plus any `.cursor/rules/`). Hard constraints; flag and fix violations.
2. **[simplify](../simplify/SKILL.md)** — mechanical pass: formatting, naming, dead code, obvious simplifications, import hygiene, docstring padding. For a dedicated mechanical-only pass the user can invoke `simplify` directly.
3. **[CODING-PREFERENCES.md](../../../CODING-PREFERENCES.md)** — durable user preferences. Apply unless they conflict with `AGENTS.md` (in which case `AGENTS.md` wins; flag the conflict).

When a change touches structure, seams, or testability, also load [improve-codebase-architecture](../improve-codebase-architecture/SKILL.md) and use its vocabulary: module, interface, depth, seam, adapter, leverage, locality.
