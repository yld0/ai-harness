# Coding preferences

## Style

- When `black` and the AGENTS.md padded-docstring rule (`""" text """`) conflict, default to `black`. The rule is currently honoured in only 1 of ~150 source files; treat the inconsistency as a separate, project-wide concern rather than enforcing it on individual PRs.

- Not a fan of underscore use for global variables or functions unless inside a class and is a private function

- Prefer f-strings for log messages too. Do not use lazy `%s` logger interpolation unless there is a concrete performance or structured-logging requirement for that specific call site.

## Architecture / design

- For registry-style components keyed by a name, raise at declaration time when the same name is re-used with conflicting settings. Prefer loud, order-independent failure over silently inheriting the first-registered settings.

- Avoid wrapper types or duplicate config shapes when an existing config object already represents the state; pass or update the existing object directly.

- only use os.env in special cases else use shared.envutil.config (config.py) for config

- Simplicity & maintainable: Prioritize clarity and maintainability over cleverness.

## Process

-
