---
name: note-taking
description: Read, search, create, and append to notes in a configurable notes directory. Backend-agnostic — works with any flat-file vault (Obsidian, plain markdown, etc.).
version: 1.0.0
metadata:
  tags: [notes, markdown, knowledge-base, obsidian]
  config:
    - key: notes.vault_path
      description: Path to the notes directory / vault
      default: "~/Documents/notes"
      env: NOTES_VAULT_PATH
---

# Note-Taking

Read, search, create, and append to markdown notes in a configurable flat-file vault.

## Location

Set via `NOTES_VAULT_PATH` environment variable. Falls back to `~/Documents/notes`.

Note: paths may contain spaces — always quote them.

```bash
VAULT="${NOTES_VAULT_PATH:-$HOME/Documents/notes}"
```

## Read a note

```bash
VAULT="${NOTES_VAULT_PATH:-$HOME/Documents/notes}"
cat "$VAULT/Note Name.md"
```

## List notes

```bash
VAULT="${NOTES_VAULT_PATH:-$HOME/Documents/notes}"

# All notes
find "$VAULT" -name "*.md" -type f

# In a specific folder
ls "$VAULT/Subfolder/"
```

## Search

```bash
VAULT="${NOTES_VAULT_PATH:-$HOME/Documents/notes}"

# By filename
find "$VAULT" -name "*.md" -iname "*keyword*"

# By content
grep -rli "keyword" "$VAULT" --include="*.md"
```

## Create a note

```bash
VAULT="${NOTES_VAULT_PATH:-$HOME/Documents/notes}"
cat > "$VAULT/New Note.md" << 'ENDNOTE'
---
created: YYYY-MM-DD
tags: []
---

# Title

Content here.
ENDNOTE
```

## Append to a note

```bash
VAULT="${NOTES_VAULT_PATH:-$HOME/Documents/notes}"
printf '\n%s\n' "New content here." >> "$VAULT/Existing Note.md"
```

## Wikilinks

Use `[[Note Name]]` syntax to link related notes. Obsidian and many other editors render these as clickable links.

## Conventions

- Use YAML frontmatter (`---`) with at least `created` and `tags` fields.
- File names: lowercase, hyphens, no spaces (`my-topic.md`).
- Link related notes with `[[wikilinks]]`.
- Date-prefix daily notes: `YYYY-MM-DD.md`.

## When to Use

- User asks to save, create, or write a note
- User asks to find or search their notes
- User wants to append new information to an existing note
- User references their vault or notes directory
