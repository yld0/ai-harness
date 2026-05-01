---
name: patch-skill
description: Propose a modification to an existing skill. Currently a governance stub — patches are queued for human review and require approval before taking effect.
version: 1.0.0
metadata:
  tags: [governance, skills, meta]
  status: governance_stub
---

# Patch Skill

Propose a modification (patch) to an existing skill in the agent's skill library.

## Current Status

This tool is a **governance stub**. Skill modifications require human review and
approval before taking effect. Calling this tool queues a patch proposal — it does
not immediately modify any skill.

```
Error code: governance_not_configured
```

If governance is not configured for this deployment, patch proposals are written to
`$MEMORY_ROOT/users/<user_id>/skill_review_queue/` as `patch-<skill-name>-<timestamp>.md`
files for manual review.

## How to Propose a Patch

When a user asks to update or fix a skill, gather:

1. **Skill name** — the `name` field from the existing `SKILL.md`.
2. **What to change** — specific section(s) to modify.
3. **Reason** — why the change is needed (bug, outdated info, improvement).
4. **Proposed new content** — the replacement text or diff.

Write a patch proposal:

```markdown
---
patch_for: <skill-name>
proposed_at: <ISO-8601>
proposed_for_user: <user_id>
source: user_request
reason: <one-line reason>
---

## Change Description

<What this patch changes and why>

## Proposed Diff

### Section: <Section Title>

**Before:**
<existing content>

**After:**
<proposed content>
```

Save to:
```
$MEMORY_ROOT/users/<user_id>/skill_review_queue/patch-<skill-name>-<timestamp>.md
```

## What Happens Next

1. The patch is queued for human review.
2. A human reviewer approves, rejects, or requests changes.
3. If approved, the skill file is updated and takes effect in the next session.

## When Governance Is Configured

When a skill governance backend is connected (future), this tool will:
- Submit the patch diff via API
- Return a patch ID and review URL
- Notify the skill owner or reviewer

Until then, the queue-to-file path above applies.

## Scope Limitations

- Patches may only modify the content of an existing `SKILL.md`.
- They may not rename skills, change the `name` frontmatter field, or delete skills.
- To rename or delete a skill, contact an administrator.
