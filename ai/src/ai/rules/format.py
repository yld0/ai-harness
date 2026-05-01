"""Render a RulesSnapshot into the rules prompt section (slot 08).

Format contract
---------------
Always-apply rules are surfaced first (the model must follow them regardless of
the conversation topic).  Manual rules follow with an explicit note that the
model should apply them when the context is relevant.

Rule body text is included verbatim; rule name (if present) is used as a
Markdown heading so the model can reference it.

Secrets policy: rule instructions may contain private user instructions; they
must **never** appear in production info-level logs.  The ``format_rules_block``
function itself does no logging.
"""

from __future__ import annotations

from ai.rules.models import Rule, RulesSnapshot


def _render_rule(rule: Rule) -> str:
    heading = f"### {rule.name}" if rule.name else "### (unnamed rule)"
    return f"{heading}\n{rule.instructions.strip()}"


def format_rules_block(snapshot: RulesSnapshot) -> str:
    """Return a ``<rules>`` XML block for the prompt, or empty string.

    An empty string signals the caller (PromptBuilder) to use its default
    placeholder.
    """
    if snapshot.is_empty:
        return ""

    sections: list[str] = []

    if snapshot.always_apply:
        rendered = "\n\n".join(_render_rule(r) for r in snapshot.always_apply)
        sections.append("## Always-apply rules\n" "The following rules must be followed in every response.\n\n" + rendered)

    if snapshot.manual:
        rendered = "\n\n".join(_render_rule(r) for r in snapshot.manual)
        sections.append("## Conditional rules\n" "Apply the following rules when the conversation topic is relevant.\n\n" + rendered)

    body = "\n\n".join(sections)
    return f"<rules>\n{body}\n</rules>"
