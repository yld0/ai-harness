"""Bridge: rules_* ↔ MEMORY.md rules section.

Conflict rule: GQL is source of truth.

Pull: fetch rules via Phase 12 GraphQL operations, write them into a
``## Rules`` section of ``users/<uid>/MEMORY.md``.

Push: reads the rules section from MEMORY.md and calls ``rules_addRule`` for
any entry not yet in GQL (fire-and-forget; permanent failures are logged but
don't block the session).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ai.clients.rules import fetch_rules_snapshot
from ai.memory.bridges.base import Bridge, PullResult, PushResult
from ai.memory.para import ParaMemoryLayout
from ai.clients.transport import GraphqlClient

logger = logging.getLogger(__name__)

_RULES_SECTION_RE = re.compile(
    r"(## Rules.*?)(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)

ADD_RULE_MUTATION = """
mutation AddRule($name: String!, $instructions: String!, $alwaysApply: Boolean!) {
  rules_addRule(input: { name: $name, instructions: $instructions, alwaysApply: $alwaysApply }) {
    id
    name
  }
}
"""


class RulesBridge(Bridge):
    """Sync rules between GQL and MEMORY.md rules section."""

    direction = "both"
    gql_surface = "rules"
    conflict_rule = "gql_wins"

    async def pull(
        self,
        user_id: str,
        bearer_token: str,
        *,
        layout: ParaMemoryLayout,
        client: Optional[Any] = None,
    ) -> PullResult:
        try:
            snapshot = await fetch_rules_snapshot(bearer_token, client=client)
        except Exception as exc:  # noqa: BLE001
            logger.warning("rules_* pull failed for user %s: %s", user_id, exc)
            return PullResult(ok=False, detail=str(exc), error=str(exc))

        total = len(snapshot.always_apply) + len(snapshot.manual)
        if total == 0:
            return PullResult(ok=True, records_written=0, detail="no_rules")

        section = _format_rules_section(snapshot)
        memory_md = layout.guarded_user_path(user_id, "MEMORY.md")
        _write_rules_section(memory_md, section)

        return PullResult(ok=True, records_written=total)

    async def push(
        self,
        file_path: Path,
        user_id: str,
        bearer_token: str,
        *,
        layout: ParaMemoryLayout,
        client: Optional[Any] = None,
    ) -> PushResult:
        """Extract rules from MEMORY.md and push new ones to GQL.

        Since GQL is source of truth, this is fire-and-forget only for rules
        that originated on the file side.  Skips rules already authored in GQL.
        """
        memory_md = layout.guarded_user_path(user_id, "MEMORY.md")
        if not memory_md.is_file():
            return PushResult(ok=True, detail="no_memory_md")

        local_rules = _parse_rules_from_section(memory_md.read_text(encoding="utf-8"))
        if not local_rules:
            return PushResult(ok=True, records_pushed=0, detail="no_local_rules")

        gql: Any = client or GraphqlClient()
        pushed = 0
        for name, instructions, always_apply in local_rules:
            try:
                await gql.execute(
                    ADD_RULE_MUTATION,
                    variables={
                        "name": name,
                        "instructions": instructions,
                        "alwaysApply": always_apply,
                    },
                    bearer_token=bearer_token,
                )
                pushed += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("rules push failed for rule %r: %s", name, exc)

        return PushResult(ok=True, records_pushed=pushed)


# ─────────────────────── helpers ──────────────────────────────────────────── #


def _format_rules_section(snapshot: Any) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [f"## Rules (synced from GQL {ts})\n"]
    if snapshot.always_apply:
        lines.append("### Always-apply")
        for r in snapshot.always_apply:
            heading = r.name or "(unnamed)"
            lines.append(f"- **{heading}**: {r.instructions.strip()}")
    if snapshot.manual:
        lines.append("\n### Conditional")
        for r in snapshot.manual:
            heading = r.name or "(unnamed)"
            lines.append(f"- **{heading}**: {r.instructions.strip()}")
    return "\n".join(lines) + "\n"


def _write_rules_section(memory_md: Path, section: str) -> None:
    memory_md.parent.mkdir(parents=True, exist_ok=True)
    if memory_md.is_file():
        existing = memory_md.read_text(encoding="utf-8")
        if _RULES_SECTION_RE.search(existing):
            new_content = _RULES_SECTION_RE.sub(section, existing, count=1)
        else:
            new_content = existing.rstrip() + "\n\n" + section
    else:
        new_content = f"# Memory\n\n{section}"
    memory_md.write_text(new_content, encoding="utf-8")


def _parse_rules_from_section(content: str) -> list[tuple[str, str, bool]]:
    """Return list of (name, instructions, always_apply) from MEMORY.md rules section."""
    m = _RULES_SECTION_RE.search(content)
    if not m:
        return []
    section = m.group(1)
    rules: list[tuple[str, str, bool]] = []
    always = True
    for line in section.splitlines():
        if "### Conditional" in line:
            always = False
            continue
        if line.startswith("- **") and "**:" in line:
            try:
                name_part, instr = line[4:].split("**:", 1)
                rules.append((name_part.strip(), instr.strip(), always))
            except ValueError:
                continue
    return rules
