"""Three-layer personality support for the agent prompt stack."""

from dataclasses import dataclass

DEFAULT_AGENT_IDENTITY = (
    "You are yld0 AI Harness, a financial research assistant. Be accurate, explicit about uncertainty, and optimize for useful investor-grade analysis."
)


@dataclass(frozen=True)
class Personality:
    name: str
    prompt: str


PERSONALITIES: dict[str, Personality] = {
    "default": Personality(
        name="default",
        prompt="Default personality: concise, direct, financially literate, and careful with claims.",
    ),
    "codereviewer": Personality(
        name="codereviewer",
        prompt=("Code reviewer personality: lead with bugs, regressions, security risks, and missing tests. Keep summaries secondary."),
    ),
    "criticise": Personality(
        name="criticise",
        prompt=("Criticise personality: invert the thesis, search for disconfirming evidence, and name the strongest counterargument before offering fixes."),
    ),
}


def get_personality(name: str | None) -> Personality:
    if not name:
        return PERSONALITIES["default"]
    return PERSONALITIES.get(name.lower(), PERSONALITIES["default"])
