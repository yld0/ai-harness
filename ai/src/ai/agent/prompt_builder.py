"""Deterministic system prompt construction for Phase 2."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Literal

from ai.agent.context_files import ContextFile, ContextFilesSnapshot
from ai.agent.modes import ModeConfig, get_mode_config
from ai.agent.personality import get_personality
from ai.skills.prompt import build_skills_prompt, DEFAULT_READ_TOOL_NAME

Channel = Literal["web", "whatsapp", "discord", "cli", "automation"]

CHANNEL_HINTS: dict[Channel, str] = {
    "web": "Channel web: use full Markdown, tables when useful, charts/components when available, and FileComponent outputs are allowed.",
    "whatsapp": "Channel whatsapp: reply in plain text, suitable for a phone screen. No Markdown headings, no tables, no FileComponent. Keep output <= 4096 chars.",
    "discord": "Channel discord: use limited Markdown only (bold, code blocks, lists), no tables, no FileComponent. Keep each message <= 2000 chars.",
    "cli": "Channel cli: full Markdown is allowed, ANSI colour is OK, but do not emit FileComponent because the CLI prints text.",
    "automation": "Channel automation: use terse structured output for downstream parsing; prefer JSON-in-code-fence only when the route declares it.",
}

FILE_COMPONENT_GUIDANCE = (
    "FileComponent guidance: when plan mode or a capable web UI needs editable artifacts, return a FileComponent with title, mime, and content."
)


@dataclass(frozen=True)
class PromptSlot:
    name: str
    content: str


@dataclass(frozen=True)
class PromptBuild:
    prompt: str
    metadata_hash: str
    slots: list[PromptSlot] = field(default_factory=list)
    mode: ModeConfig | None = None
    channel: Channel = "web"
    tools_enabled: bool = True
    file_components_allowed: bool = True


class PromptBuilder:
    def build(
        self,
        *,
        context: ContextFilesSnapshot,
        mode: str = "auto",
        channel: Channel = "web",
        user_system_message: str | None = None,
        memory_snapshot: str = "",
        user_profile: str = "",
        external_memory: str = "",
        skills_xml: str = "",
        rules_block: str = "",
        personality_name: str | None = None,
        ephemeral_system_prompt: str | None = None,
        now: datetime | None = None,
    ) -> PromptBuild:
        mode_config = get_mode_config(mode)
        personality = get_personality(personality_name or ("criticise" if mode == "criticise" else None))
        now = now or datetime.now(timezone.utc)
        file_components_allowed = channel == "web"

        skills_index = skills_xml.strip() if skills_xml else build_skills_prompt([], read_tool_name=DEFAULT_READ_TOOL_NAME).prompt_text
        slots = [
            PromptSlot("01_identity", context.identity),
            PromptSlot(
                "02_tool_guidance",
                self._tool_guidance(mode_config.tools_enabled, file_components_allowed),
            ),
            PromptSlot("03_user_system_message", user_system_message or "[none]"),
            PromptSlot("04_memory_context", self._memory_block(memory_snapshot)),
            PromptSlot("05_user_profile", user_profile or "[none]"),
            PromptSlot("06_external_memory", external_memory or "[none]"),
            PromptSlot("07_skills_index", skills_index),
            PromptSlot(
                "08_rules",
                rules_block or "<rules>[pending phase 12 rules cache]</rules>",
            ),
            PromptSlot("09_context_files", self._context_files_block(context.files)),
            PromptSlot("10_datetime", now.isoformat()),
            PromptSlot("11_channel_hint", CHANNEL_HINTS[channel]),
            PromptSlot("12_mode", mode_config.system_delta),
            PromptSlot("13_personality", personality.prompt),
            PromptSlot("14_ephemeral", ephemeral_system_prompt or "[none]"),
        ]
        prompt = "\n\n".join(f"<{slot.name}>\n{slot.content}\n</{slot.name}>" for slot in slots)
        return PromptBuild(
            prompt=prompt,
            metadata_hash=sha256(prompt.encode("utf-8")).hexdigest(),
            slots=slots,
            mode=mode_config,
            channel=channel,
            tools_enabled=mode_config.tools_enabled,
            file_components_allowed=file_components_allowed,
        )

    @staticmethod
    def _tool_guidance(tools_enabled: bool, file_components_allowed: bool) -> str:
        parts = [
            ("Tools are enabled." if tools_enabled else "Tools are disabled for this mode."),
            "Use tool calls only when they materially improve correctness.",
        ]
        if file_components_allowed:
            parts.append(FILE_COMPONENT_GUIDANCE)
        else:
            parts.append("FileComponent guidance: disabled for this channel.")
        return "\n".join(parts)

    @staticmethod
    def _memory_block(memory_snapshot: str) -> str:
        if memory_snapshot.strip().startswith("<memory-context>"):
            return memory_snapshot
        body = memory_snapshot or "[pending phase 4 memory snapshot]"
        return f"<memory-context>\n{body}\n</memory-context>"

    @staticmethod
    def _context_files_block(files: list[ContextFile]) -> str:
        if not files:
            return "[none]"
        rendered = []
        for file in files:
            rendered.append(f'<context-file path="{file.path}">\n{file.content}\n</context-file>')
        return "\n\n".join(rendered)
