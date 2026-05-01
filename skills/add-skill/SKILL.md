---
name: add-skill
description: Propose a new skill to be added to the skill library. Currently a governance stub — proposals are queued for human review and require approval before activation.
version: 1.0.0
metadata:
  tags: [governance, skills, meta]
  status: governance_stub
---

# Add Skill

Propose a new skill to be added to the agent's skill library.

## Current Status

This tool is a **governance stub**. Skill creation requires human review and approval
before the skill becomes active. Calling this tool queues a proposal — it does not
immediately add any skill.

```
Error code: governance_not_configured
```

If governance is not configured for this deployment, skill proposals are written to
`$MEMORY_ROOT/users/<user_id>/skill_review_queue/` as `proposed-<timestamp>.md`
files for manual review.

## How to Propose a Skill

When a user asks to add a skill, gather the following information and write a
`SKILL.md` draft:

```yaml
---
name: <skill-name>          # kebab-case, unique
description: <one-line>     # shown in skill list
version: 1.0.0
metadata:
  tags: []
  status: pending_review
  proposed_at: <ISO-8601>
  proposed_for_user: <user_id>
  source: user_request
---
```

Then describe:

1. **What the skill does** — the core capability in plain language.
2. **When it should activate** — trigger conditions or slash command.
3. **Tools it uses** — which existing tools it calls.
4. **Prerequisites** — env vars, binaries, or API keys required.
5. **Example usage** — one worked example showing input → output.

Save the draft to:
```
$MEMORY_ROOT/users/<user_id>/skill_review_queue/proposed-<timestamp>.md
```

## What Happens Next

1. The draft is queued for human review.
2. A human reviewer approves, rejects, or requests changes.
3. If approved, the skill is added to `skills/<name>/SKILL.md` and becomes
   discoverable in the next session.

## When Governance Is Configured

When a skill governance backend is connected (future), this tool will:
- Submit the proposal via API
- Return a proposal ID and review URL
- Notify the reviewer

Until then, the queue-to-file path above applies.
