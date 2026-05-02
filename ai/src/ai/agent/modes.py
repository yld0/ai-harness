"""Agent mode configuration and system-prompt deltas."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

AgentMode = Literal["auto", "plan", "explain", "criticise"]
ProviderEffort = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class ModeConfig:
    name: AgentMode
    effort: ProviderEffort
    tools_enabled: bool
    system_delta: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _read_skill_xml(skill_name: str, relative_path: str, *, limit: int = 6000) -> str:
    path = _repo_root() / relative_path
    try:
        body = path.read_text(encoding="utf-8").strip()
    except OSError:
        body = f"# {skill_name}\nSkill body unavailable in this checkout."
    if len(body) > limit:
        body = body[:limit].rstrip() + "\n[truncated]"
    return f'<skill name="{skill_name}">\n{body}\n</skill>'


PLAN_PREAMBLE = "\n\n".join(
    [
        "Plan mode: inspect context, produce a concrete Markdown plan, and surface it as a FileComponent for user editing.",
        _read_skill_xml(
            "plan",
            "references/hermes-agent-main/skills/software-development/plan/SKILL.md",
        ),
        _read_skill_xml(
            "writing-plans",
            "references/hermes-agent-main/skills/software-development/writing-plans/SKILL.md",
        ),
    ]
)

CRITICISE_PREAMBLE = (
    "Criticise mode: act as a risk-focused reviewer. Stress-test assumptions, " "look for hidden failure modes, and separate evidence from speculation."
)

EXPLAIN_PREAMBLE = "Explain mode: answer directly in text. Do not call tools; prioritize clarity, " "definitions, and concise examples."


MODE_CONFIGS: dict[AgentMode, ModeConfig] = {
    "auto": ModeConfig(
        name="auto",
        effort="low",
        tools_enabled=True,
        system_delta="Auto mode: use the lowest sufficient effort and tools only when they materially improve the answer.",
    ),
    "plan": ModeConfig(
        name="plan",
        effort="high",
        tools_enabled=True,
        system_delta=PLAN_PREAMBLE,
    ),
    "explain": ModeConfig(
        name="explain",
        effort="low",
        tools_enabled=False,
        system_delta=EXPLAIN_PREAMBLE,
    ),
    "criticise": ModeConfig(
        name="criticise",
        effort="high",
        tools_enabled=True,
        system_delta=CRITICISE_PREAMBLE,
    ),
}


def get_mode_config(mode: str | None) -> ModeConfig:
    if mode in MODE_CONFIGS:
        return MODE_CONFIGS[mode]  # type: ignore[index]
    return MODE_CONFIGS["auto"]
