import asyncio
from pathlib import Path

from ai.agent.context_files import ContextFilesLoader
from ai.agent.loop import ProviderMessage, ProviderTurn
from ai.agent.runner import AgentRunner
from ai.memory.loader import MemoryLoader
from ai.memory.para import ParaMemoryLayout
from ai.schemas.agent import AgentChatRequest


class CapturingProvider:
    def __init__(self, text: str = "captured final") -> None:
        self.text = text
        self.calls: list[dict] = []

    async def complete(self, messages: list[ProviderMessage], *, tools_enabled: bool, effort: str) -> ProviderTurn:
        self.calls.append(
            {
                "messages": messages,
                "tools_enabled": tools_enabled,
                "effort": effort,
            }
        )
        return ProviderTurn(
            content=self.text,
            finish_reason="stop",
            metadata={"provider": "capturing"},
        )


def request_payload(mode: str = "auto", route_metadata: dict | None = None) -> dict:
    return {
        "conversationID": "conversation-1",
        "request": {"query": "Build a plan for valuation workflows"},
        "context": {"route": "chats", "routeMetadata": route_metadata or {}},
        "mode": mode,
    }


def runner_with_provider(provider: CapturingProvider, memory_loader: MemoryLoader | None = None) -> AgentRunner:
    return AgentRunner(
        provider=provider,
        context_loader=ContextFilesLoader(Path(__file__).resolve().parents[2]),
        memory_loader=memory_loader,
    )


# TODO: Add test for plan mode
# def test_plan_mode_bootstraps_writing_plans_skill_and_returns_file_component() -> None:
#     async def run() -> None:
#         provider = CapturingProvider("plan response")
#         runner = runner_with_provider(provider)
#         response = await runner.question(
#             AgentChatRequest.model_validate(request_payload("plan")),
#             user_id="user-1",
#         )

#         system_prompt = provider.calls[0]["messages"][0].content
#         assert '<skill name="plan">' in system_prompt
#         assert '<skill name="writing-plans">' in system_prompt
#         assert "Writing Implementation Plans" in system_prompt
#         assert provider.calls[0]["effort"] == "high"
#         assert response.response.components
#         assert response.response.components[0].type == "file"
#         assert response.metadata["mode"] == "plan"

#     asyncio.run(run())


def test_explain_mode_disables_tools() -> None:
    async def run() -> None:
        provider = CapturingProvider()
        runner = runner_with_provider(provider)
        response = await runner.question(
            AgentChatRequest.model_validate(request_payload("explain")),
            user_id="user-1",
        )

        assert provider.calls[0]["tools_enabled"] is False
        assert response.metadata["tools_enabled"] is False

    asyncio.run(run())


def test_criticise_mode_uses_criticise_preamble() -> None:
    async def run() -> None:
        provider = CapturingProvider()
        runner = runner_with_provider(provider)
        await runner.question(
            AgentChatRequest.model_validate(request_payload("criticise")),
            user_id="user-1",
        )

        system_prompt = provider.calls[0]["messages"][0].content
        assert "Criticise mode" in system_prompt
        assert "Criticise personality" in system_prompt

    asyncio.run(run())


def test_runner_uses_channel_hint_from_route_metadata() -> None:
    async def run() -> None:
        provider = CapturingProvider()
        runner = runner_with_provider(provider)
        await runner.question(
            AgentChatRequest.model_validate(request_payload("auto", {"channel": "whatsapp"})),
            user_id="user-1",
        )

        system_prompt = provider.calls[0]["messages"][0].content
        assert "Channel whatsapp" in system_prompt
        assert "no FileComponent" in system_prompt

    asyncio.run(run())


def test_runner_injects_frozen_hot_memory_snapshot(tmp_path) -> None:
    async def run() -> None:
        layout = ParaMemoryLayout(tmp_path)
        root = layout.ensure_user_layout("user-1")
        (root / "MEMORY.md").write_text("Initial memory", encoding="utf-8")
        provider = CapturingProvider()
        runner = runner_with_provider(provider, MemoryLoader(layout))
        request = AgentChatRequest.model_validate(request_payload("auto"))

        await runner.question(request, user_id="user-1")
        (root / "MEMORY.md").write_text("Changed memory", encoding="utf-8")
        await runner.question(request, user_id="user-1")

        first_prompt = provider.calls[0]["messages"][0].content
        second_prompt = provider.calls[1]["messages"][0].content
        assert "Initial memory" in first_prompt
        assert "Initial memory" in second_prompt
        assert "Changed memory" not in second_prompt

    asyncio.run(run())
