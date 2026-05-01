"""Central AgentRunner orchestration boundary for the v3 API surface."""

import logging
import time
from functools import wraps
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from ai.config import agent_config

from ai.agent.context_files import ContextFilesLoader
from ai.agent.loop import (
    Provider,
    ProviderMessage,
    ToolRegistry,
    run_turn_loop,
)
from ai.agent.progress import NoopProgressSink, ProgressSink
from ai.agent.prompt_builder import Channel, PromptBuilder
from ai.memory.loader import MemoryLoader
from ai.memory.para import ParaMemoryLayout
from ai.memory.writer import MemoryWriter
from ai.skills.registry import build_skills_system_block
from ai.skills.types import SessionPermission
from ai.providers.router import ProviderRouter
import ai.commands  # noqa: F401
from ai.commands.base import CommandResult, get_handler, register_builtins
from ai.commands.parser import parse_slash_command
from ai.routes.registry import ROUTE_MODULE_PATHS
from ai.routes.dispatch import dispatch as _dispatch_route
from ai.routes.context import RouteContext
from ai.rules.cache import RulesCache
from ai.rules.format import format_rules_block
from ai.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    ChatResponse,
    FileComponent,
)
from ai.context import BEARER_TOKEN, CONVERSATION_ID, REQUEST_ID
from ai.tools.context import ToolContext, reset_tool_context, set_tool_context
from ai.tools.registry import list_openai_tools, register_tools
from ai.telemetry import capture_event
from ai.telemetry.langfuse import (
    LangfuseProviderWrapper,
    LangfuseToolRegistryWrapper,
    agent_run_observation,
    get_langfuse_client,
)
from ai.telemetry.redact import redact_settings_from_env, redact_value

logger = logging.getLogger(__name__)


@dataclass
class AgentTurnResult:
    """One completed agent turn: response, message transcript, and turn index for hooks."""

    response: AgentChatResponse
    messages: list[ProviderMessage]
    user_id: str
    request: AgentChatRequest
    loop_metadata: dict[str, Any]
    user_message: str
    turn_index: int = 0


def with_response_time(func):
    """Decorator that adds response_time_ms to AgentChatResponse.metadata."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        if isinstance(result, AgentTurnResult):
            result.response.metadata["response_time_ms"] = round((time.perf_counter() - start) * 1000)
        return result

    return wrapper


class AgentRunner:
    def __init__(
        self,
        *,
        provider: Provider | None = None,
        tools: ToolRegistry | None = None,
        prompt_builder: PromptBuilder | None = None,
        context_loader: ContextFilesLoader | None = None,
        memory_loader: MemoryLoader | None = None,
        rules_cache: RulesCache | None = None,
    ) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        # Register built-in slash command handlers (idempotent via replace=True).
        register_builtins(replace=True)
        self.provider = provider or self._default_provider()
        if tools is None:
            tr = ToolRegistry()
            register_tools(tr)
            self.tools = tr
        else:
            self.tools = tools
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.context_loader = context_loader or ContextFilesLoader(repo_root)
        self.memory_loader = memory_loader or MemoryLoader()
        self.rules_cache = rules_cache or RulesCache()
        self._turn_seq: dict[tuple[str, str], int] = {}

    async def question(
        self,
        request: AgentChatRequest,
        *,
        user_id: str,
        bearer_token: str | None = None,
        progress: ProgressSink | None = None,
    ) -> AgentChatResponse:
        return await self.run_chat(request, user_id=user_id, bearer_token=bearer_token, progress=progress)

    async def run(
        self,
        request: AgentChatRequest,
        *,
        user_id: str,
        bearer_token: str | None = None,
        progress: ProgressSink | None = None,
    ) -> AgentChatResponse:
        return await self.run_automation(request, user_id=user_id, bearer_token=bearer_token, progress=progress)

    async def run_chat(
        self,
        request: AgentChatRequest,
        *,
        user_id: str,
        bearer_token: str | None = None,
        progress: ProgressSink | None = None,
    ) -> AgentChatResponse:
        return (await self.run_chat_turn(request, user_id=user_id, bearer_token=bearer_token, progress=progress)).response

    @with_response_time
    async def run_chat_turn(
        self,
        request: AgentChatRequest,
        *,
        user_id: str,
        bearer_token: str | None = None,
        progress: ProgressSink | None = None,
    ) -> AgentTurnResult:
        query = getattr(request.request, "query", "") or ""
        sc = getattr(request, "slash_command", None)

        # 1. Determine command name + args — prefer structured slash_command field,
        #    then fall back to detecting a leading "/" in the user text.
        cmd_name: str | None = None
        cmd_args: list[str] = []
        if sc is not None:
            cmd_name = sc.name.lower()
            cmd_args = list(sc.args)
        else:
            parsed = parse_slash_command(query)
            if parsed is not None:
                cmd_name = parsed.name
                cmd_args = parsed.args

        # 2. Dispatch to registered handler.
        if cmd_name is not None:
            handler = get_handler(cmd_name)
            if handler is not None:
                ctx: dict[str, Any] = {
                    "repo_root": Path(self.context_loader.root),
                    "user_id": user_id,
                    "request": request,
                }
                try:
                    result = await handler.handle(cmd_args, context=ctx)
                except Exception as exc:  # noqa: BLE001
                    result = CommandResult(
                        text=f"/{cmd_name} failed: {exc}",
                        dispatched=True,
                        error=str(exc),
                    )
                return self._command_result_to_turn(result, request, user_id=user_id, cmd_name=cmd_name)
            # 3. Unknown command — pass to LLM with a note in the metadata.
            return await self._run_request(
                request,
                user_message=query,
                user_id=user_id,
                bearer_token=bearer_token,
                progress=progress,
                extra_metadata={"slash_command_passthrough": cmd_name},
            )

        return await self._run_request(
            request,
            user_message=query,
            user_id=user_id,
            bearer_token=bearer_token,
            progress=progress,
        )

    async def run_automation(
        self,
        request: AgentChatRequest,
        *,
        user_id: str,
        bearer_token: str | None = None,
        progress: ProgressSink | None = None,
    ) -> AgentChatResponse:
        route = getattr(request, "route", None) or request.context.route or "automation"
        rid = request.conversation_id or getattr(request, "automation_run_id", None)
        if rid is None:
            raise ValueError("conversation_id is required")
        payload: dict[str, Any] = getattr(request, "input", None) or {}
        sink = progress or NoopProgressSink()

        # Dispatch registered Phase-14 routes through the dedicated handler system.
        if route in ROUTE_MODULE_PATHS:
            mem_root = Path(agent_config.MEMORY_ROOT).expanduser().resolve()
            layout = ParaMemoryLayout(mem_root)
            writer = MemoryWriter(layout)
            route_ctx = RouteContext(
                user_id=user_id,
                request=request,
                bearer_token=bearer_token,
                input=dict(payload),
                layout=layout,
                writer=writer,
                progress=sink,
                call_llm=self._make_llm_caller(request, user_id=user_id, bearer_token=bearer_token, progress=sink),
            )
            result = await _dispatch_route(route, route_ctx)
            meta: dict[str, Any] = {
                "route": route,
                "route_status": "ok" if result.ok else "error",
                "runner": "phase-14",
                "user_id": user_id,
                "automation_run_id": getattr(request, "automation_run_id", None),
                **result.metadata,
            }
            if not result.ok:
                meta["error"] = {
                    "code": result.error or "route_error",
                    "message": result.text,
                }
            return AgentChatResponse(
                conversation_id=rid,
                response=ChatResponse(text=result.text, metadata=meta),
                metadata=meta,
            )

        # Unknown/unregistered route — fall back to generic LLM turn.
        user_message = f"Automation route: {route}\nInput: {payload}"
        return (
            await self._run_request(
                request,
                user_message=user_message,
                user_id=user_id,
                bearer_token=bearer_token,
                progress=progress,
                route=route,
                extra_metadata={
                    "input": payload,
                    "automation_run_id": getattr(request, "automation_run_id", None),
                },
            )
        ).response

    def _make_llm_caller(
        self,
        request: AgentChatRequest,
        *,
        user_id: str,
        bearer_token: str | None,
        progress: ProgressSink,
    ):
        """Return a single-argument async callable that does one LLM turn."""

        async def _call_llm(prompt: str) -> str:
            result = await self._run_request(
                request,
                user_message=prompt,
                user_id=user_id,
                bearer_token=bearer_token,
                progress=progress,
            )
            return result.response.response.text or ""

        return _call_llm

    async def _run_request(
        self,
        request: AgentChatRequest,
        *,
        user_message: str,
        user_id: str,
        bearer_token: str | None,
        progress: ProgressSink | None,
        route: str | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> AgentTurnResult:
        sink = progress or NoopProgressSink()
        session_id = request.conversation_id or getattr(request, "automation_run_id", None) or "default"
        display_conv_id = request.conversation_id or getattr(request, "automation_run_id", None)
        if display_conv_id is None:
            raise ValueError("conversation_id is required")
        await sink.emit("conversation_id", {"conversation_id": display_conv_id})
        await sink.emit(
            "task_progress",
            {
                "task_id": "agent-turn",
                "title": "Agent turn",
                "items": [{"type": "item", "content": "Running agent…"}],
                "default_open": True,
            },
        )
        hot_memory = self.memory_loader.load_hot_snapshot(
            user_id=user_id,
            session_id=session_id,
            first_message=user_message,
        )
        rules_snapshot = await self.rules_cache.load(user_id, bearer_token)
        rules_block = format_rules_block(rules_snapshot)
        skills_block = build_skills_system_block(
            Path(self.context_loader.root),
            read_tool_name=agent_config.AI_READ_TOOL_NAME,
            max_prompt_chars=agent_config.AI_SKILLS_INDEX_MAX_CHARS,
            session_permission=self._session_permission(request),
        )
        prompt = self.prompt_builder.build(
            context=self.context_loader.load(),
            mode=getattr(request, "mode", "auto"),
            channel=self._channel(request),
            user_system_message=self._user_system_message(request),
            memory_snapshot=hot_memory.content,
            user_profile=hot_memory.user_profile,
            skills_xml=skills_block.prompt_text,
            rules_block=rules_block,
            personality_name=self._personality_name(request),
            ephemeral_system_prompt=self._ephemeral_system_prompt(request),
        )
        messages = [
            ProviderMessage(role="system", content=prompt.prompt),
            ProviderMessage(role="user", content=user_message),
        ]
        model_override = getattr(request.request, "model", None)
        request_thinking = getattr(request, "mode", "auto") == "criticise" or (prompt.mode is not None and prompt.mode.effort == "high")
        effective_route = str(route or request.context.route or "")
        openai_tools = list_openai_tools(
            session=str(self._session_permission(request)),
            channel=self._channel(request),
            route=effective_route,
        )
        provider = self._provider_for_request(
            model_override=model_override,
            request_thinking=request_thinking,
            tools=openai_tools,
            metadata={
                "user_id": user_id,
                "conversation_id": request.conversation_id,
                "route": route or request.context.route,
                "mode": getattr(request, "mode", "auto"),
            },
        )
        mem_root = Path(agent_config.MEMORY_ROOT).expanduser().resolve()
        tool_ctx = ToolContext(
            user_id=user_id,
            session_id=session_id,
            session_permission=self._session_permission(request),
            channel=self._channel(request),
            route=effective_route,
            progress=sink,
            bearer_token=bearer_token,
            memory_root=mem_root,
            project_root=Path(self.context_loader.root),
            request_id=REQUEST_ID.get(),
            request_metadata=dict(request.context.route_metadata or {}),
        )
        bearer_token_ctx = BEARER_TOKEN.set(bearer_token)
        conversation_id_ctx = CONVERSATION_ID.set(request.conversation_id)
        token = set_tool_context(tool_ctx)
        lf = get_langfuse_client()
        tsettings = redact_settings_from_env()
        trace_name = "run_automation" if route is not None else "run_chat"
        input_summary = {
            "user_message": redact_value(user_message, tsettings, mode="prompt"),
            "route": route or str(request.context.route or ""),
            "conversation_id": str(request.conversation_id or ""),
        }
        provider_exec = LangfuseProviderWrapper(provider, lf, tsettings) if lf is not None else provider
        tools_exec = LangfuseToolRegistryWrapper(self.tools, lf, tsettings) if lf is not None else self.tools
        try:
            with agent_run_observation(
                lf,
                user_id=user_id,
                session_id=session_id,
                trace_name=trace_name,
                input_summary=input_summary,
            ):
                loop_result = await run_turn_loop(
                    provider=provider_exec,
                    messages=messages,
                    tools=tools_exec,
                    tools_enabled=prompt.tools_enabled,
                    effort=prompt.mode.effort if prompt.mode is not None else "low",
                    progress=sink,
                )
        finally:
            reset_tool_context(token)
            BEARER_TOKEN.reset(bearer_token_ctx)
            CONVERSATION_ID.reset(conversation_id_ctx)
        u_raw = loop_result.metadata.get("usage") or {}
        usage_dict = u_raw if isinstance(u_raw, dict) else {}
        model_id = loop_result.metadata.get("model") or loop_result.metadata.get("provider") or (loop_result.metadata.get("metadata") or {}).get("model")
        await sink.emit(
            "usage",
            {
                "prompt_tokens": usage_dict.get("prompt_tokens"),
                "completion_tokens": usage_dict.get("completion_tokens"),
                "total_tokens": usage_dict.get("total_tokens"),
                "model": model_id,
            },
        )
        await sink.emit(
            "task_progress_summary",
            {"task_id": "agent-turn", "summary": "Turn complete."},
        )
        components = self._components_for_mode(request, loop_result.text)
        metadata = {
            "runner": "phase-6",
            "user_id": user_id,
            "route": route or request.context.route,
            "mode": getattr(request, "mode", "auto"),
            "channel": prompt.channel,
            "prompt_hash": prompt.metadata_hash,
            "provider_effort": prompt.mode.effort if prompt.mode is not None else "low",
            "tools_enabled": prompt.tools_enabled,
            "memory_snapshot": hot_memory.metadata,
            "iterations": loop_result.iterations,
            "finish_reason": loop_result.finish_reason,
            **loop_result.metadata,
            **(extra_metadata or {}),
        }
        turn_index = self._bump_turn(user_id, session_id)
        capture_event(
            user_id,
            "agent_turn_completed",
            {
                "trace_name": trace_name,
                "route": str(route or request.context.route or ""),
                "iterations": loop_result.iterations,
                "finish_reason": loop_result.finish_reason,
                "channel": prompt.channel,
            },
        )
        out = AgentChatResponse(
            conversation_id=display_conv_id,
            response=ChatResponse(
                text=loop_result.text,
                components=components,
                metadata=metadata,
            ),
            metadata=metadata,
        )
        return AgentTurnResult(
            response=out,
            messages=loop_result.messages,
            user_id=user_id,
            request=request,
            loop_metadata=dict(metadata),
            user_message=user_message,
            turn_index=turn_index,
        )

    def _bump_turn(self, user_id: str, session_id: str) -> int:
        key = (user_id, session_id)
        n = self._turn_seq.get(key, 0) + 1
        self._turn_seq[key] = n
        return n

    @staticmethod
    def _default_provider() -> Provider:
        if not (agent_config.GENAI_API_KEY or agent_config.OPENROUTER_API_KEY):
            raise RuntimeError("No LLM API key configured. Set GENAI_API_KEY or OPENROUTER_API_KEY.")
        return ProviderRouter(fallback_models=agent_config.AI_FALLBACK_MODELS)

    def _provider_for_request(
        self,
        *,
        model_override: str | None,
        request_thinking: bool,
        tools: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any],
    ) -> Provider:
        with_options = getattr(self.provider, "with_options", None)
        if callable(with_options):
            return with_options(
                model_override=model_override,
                tools=tools,
                request_thinking=request_thinking,
                metadata=metadata,
            )
        return self.provider

    def _components_for_mode(self, request: AgentChatRequest, text: str) -> list[FileComponent]:
        if getattr(request, "mode", "auto") != "plan":
            return []
        query = getattr(request.request, "query", "requested work")
        content = (
            f"# Draft Plan\n\n"
            f"## Goal\n{query}\n\n"
            f"## Proposed Approach\n{text}\n\n"
            "## Verification\n- Add or update focused tests.\n- Run the relevant test suite.\n"
        )
        return [
            FileComponent(
                title="Draft implementation plan",
                mime="text/markdown",
                content=content,
            )
        ]

    def _command_result_to_turn(
        self,
        result: CommandResult,
        request: AgentChatRequest,
        *,
        user_id: str,
        cmd_name: str,
    ) -> AgentTurnResult:
        metadata: dict[str, Any] = {
            "runner": "phase-11",
            "user_id": user_id,
            "slash_command": cmd_name,
            "dispatched": result.dispatched,
            "side_effects": result.side_effects,
        }
        if result.error:
            metadata["error"] = result.error
        conv_id = request.conversation_id
        if conv_id is None:
            raise ValueError("conversation_id is required")
        return AgentTurnResult(
            response=AgentChatResponse(
                conversation_id=conv_id,
                response=ChatResponse(text=result.text, metadata=metadata),
                metadata=metadata,
            ),
            messages=[],
            user_id=user_id,
            request=request,
            loop_metadata=metadata,
            user_message="",
            turn_index=0,
        )

    @staticmethod
    def _session_permission(request: AgentChatRequest) -> SessionPermission:
        route_metadata = request.context.route_metadata or {}
        raw = route_metadata.get("sessionPermission") or route_metadata.get("permissionMode")
        if raw is not None and str(raw) == "ReadOnly":
            return "ReadOnly"
        return "ReadWrite"

    @staticmethod
    def _channel(request: AgentChatRequest) -> Channel:
        route_metadata = request.context.route_metadata or {}
        channel = route_metadata.get("channel") or getattr(request, "channel", None) or "web"
        if channel in {"web", "whatsapp", "discord", "cli", "automation"}:
            return cast(Channel, channel)
        return "web"

    @staticmethod
    def _personality_name(request: AgentChatRequest) -> str | None:
        route_metadata = request.context.route_metadata or {}
        value = route_metadata.get("personality")
        return str(value) if value else None

    @staticmethod
    def _ephemeral_system_prompt(request: AgentChatRequest) -> str | None:
        route_metadata = request.context.route_metadata or {}
        value = route_metadata.get("ephemeralSystemPrompt") or route_metadata.get("ephemeral_system_prompt")
        return str(value) if value else None

    @staticmethod
    def _user_system_message(request: AgentChatRequest) -> str | None:
        route_metadata = request.context.route_metadata or {}
        value = route_metadata.get("systemMessage") or route_metadata.get("system_message")
        return str(value) if value else None
