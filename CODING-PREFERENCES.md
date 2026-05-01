# Coding preferences

## Style

- When `black` and the AGENTS.md padded-docstring rule (`""" text """`) conflict, default to `black`. The rule is currently honoured in only 1 of ~150 source files; treat the inconsistency as a separate, project-wide concern rather than enforcing it on individual PRs.

- Not a fan of underscore use for global variables or functions unless inside a class and is a private function

## Architecture / design

- For registry-style components keyed by a name, raise at declaration time when the same name is re-used with conflicting settings. Prefer loud, order-independent failure over silently inheriting the first-registered settings.

## Process

-
