from datetime import datetime, timezone

from ai.agent.context_files import ContextFile, ContextFilesSnapshot
from ai.agent.prompt_builder import CHANNEL_HINTS, PromptBuilder


def snapshot() -> ContextFilesSnapshot:
    return ContextFilesSnapshot(
        identity="IDENTITY",
        files=[ContextFile(path="AGENTS.md", content="PROJECT RULES")],
    )


def test_prompt_slot_order_and_hash_is_deterministic() -> None:
    builder = PromptBuilder()
    now = datetime(2026, 4, 26, tzinfo=timezone.utc)

    first = builder.build(
        context=snapshot(),
        mode="auto",
        channel="web",
        memory_snapshot="MEMORY",
        rules_block="RULES",
        now=now,
    )
    second = builder.build(
        context=snapshot(),
        mode="auto",
        channel="web",
        memory_snapshot="MEMORY",
        rules_block="RULES",
        now=now,
    )

    assert first.metadata_hash == second.metadata_hash
    markers = [
        "<01_identity>",
        "<02_tool_guidance>",
        "<03_user_system_message>",
        "<04_memory_context>",
        "<07_skills_index>",
        "<08_rules>",
        "<09_context_files>",
        "<10_datetime>",
        "<11_channel_hint>",
        "<12_mode>",
        "<13_personality>",
        "<14_ephemeral>",
    ]
    positions = [first.prompt.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_channel_hints_and_file_component_guidance() -> None:
    builder = PromptBuilder()

    for channel, hint in CHANNEL_HINTS.items():
        built = builder.build(context=snapshot(), channel=channel)
        assert hint in built.prompt
        if channel == "web":
            assert "FileComponent outputs are allowed" in built.prompt
            assert built.file_components_allowed is True
        else:
            assert "no FileComponent" in built.prompt or "disabled for this channel" in built.prompt
            assert built.file_components_allowed is False


def test_personality_overlay_appears_after_context_files() -> None:
    built = PromptBuilder().build(
        context=snapshot(),
        personality_name="codereviewer",
    )

    assert built.prompt.index("<13_personality>") > built.prompt.index("<09_context_files>")
    assert "Code reviewer personality" in built.prompt


# TODO: Add test for modes
# def test_modes_affect_tools_and_preamble() -> None:
#     explain = PromptBuilder().build(context=snapshot(), mode="explain")
#     plan = PromptBuilder().build(context=snapshot(), mode="plan")
#     criticise = PromptBuilder().build(context=snapshot(), mode="criticise")

#     assert explain.tools_enabled is False
#     assert "Tools are disabled for this mode." in explain.prompt
#     assert '<skill name="plan">' in plan.prompt
#     assert '<skill name="writing-plans">' in plan.prompt
#     assert "Writing Implementation Plans" in plan.prompt
#     assert "Criticise mode" in criticise.prompt
