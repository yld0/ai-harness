---
name: ai-slop
description: Cleans a branch by comparing to main and stripping AI-style noise from the diff—redundant comments, abnormal defensive code, any-casts, and local style drift. Use when the user asks to remove AI slop, clean up a branch or PR, or sanitize changes before review.
disable-model-invocation: true
---

# Remove AI code slop

Check the diff against main, and remove all AI generated slop introduced in this branch.

This includes:

- Extra comments that a human wouldn't add or is inconsistent with the rest of the file
- Extra defensive checks or try/catch blocks that are abnormal for that area of the codebase (especially if called by trusted / validated codepaths)
- Casts to any to get around type issues
- Any other style that is inconsistent with the file

Report at the end with only a 1-3 sentence summary of what you changed

## Workflow

- Use `git diff main...HEAD` when `main` exists; otherwise use the repository’s default branch name instead of `main`.
- Limit edits to lines or patterns introduced on this branch; match each file’s existing style.
- Prefer proper types over `Any`; avoid drive-by refactors.


