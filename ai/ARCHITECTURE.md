# AI harness architecture

This document maps the `ai/` package (`src/ai/`) for code review: HTTP/WebSocket surface, `AgentRunner`, the provider/tool loop, and major subsystems.

## App shell and API surface

- **`main.py`** — FastAPI app: CORS, lifespan wires **`AgentRunner`**, **`WSConnectionManager`**, **`HookRunner`**, and **`setup_telemetry`**. Includes health routers, v3 HTTP routes, and **`WS /v3/ws/{client_id}`**.
- **`api/routes.py`** — **`POST /v3/agent/question`**: JWT (`sub` → `user_id`), optional Bearer forward to tools, **`run_chat_turn`**, then **background** **`HookRunner.run_after_response`**.
- **`api/automation_routes.py`** — Automation path (e.g. idempotency, **`POST /v3/agent/run`**) using the same runner with automation-specific request shapes.
- **`api/auth.py`** — Bearer JWT validation; **`optional_bearer_token`** for GraphQL-oriented tools.
- **`config.py`** — Port/reload, **`GATEWAY_URL`**, Mongo/Redis/urlmeta, **telemetry**, and **council** settings.
- **`middleware/request_id.py`** — **`X-Request-ID`**: honors inbound header or generates UUID; sets **`request.state.request_id`** and a **`ContextVar`** for the request task. **`ToolContext.request_id`** is filled from **`get_request_id()`** during **`_run_request`**. WebSocket turns set the ContextVar for the duration of **`run_chat_turn`** + response/hooks when HTTP did not already bind one.

## Schemas and contract

- **`schemas/agent_v3.py`** — Additive v3 request/response (modes, slash commands, automation envelope, etc.).
- **`schemas/agent_v2.py`** — Verbatim reference compatibility; not the live v3 orchestration path.

## AgentRunner (orchestration boundary)

Central type: **`agent/runner.py`** — **`AgentRunner`**.

| Entry | Role |
|--------|------|
| **`question` / `run_chat`** | User chat → **`run_chat_turn`** → **`_run_request`** (unless a slash command handles the turn). |
| **`run` / `run_automation`** | Automations: if **`route`** is in the Phase-14 registry → **`routes.dispatch`**; else synthetic user message + **`_run_request`**. |
| **`run_chat_turn`** | Parses slash commands (structured field or leading `/`); **`commands`** registry or **`_run_request`**; returns **`AgentTurnResult`** (response + message transcript for hooks). |

Slash commands live under **`commands/`** with **`commands/parser.py`** and **`get_handler`**; unknown commands pass through to the LLM with metadata.

## Main loop

### `_run_request` (one harness “turn”)

Approximate order:

1. **Progress** — `conversation_id`, `task_progress`.
2. **Memory** — **`MemoryLoader.load_hot_snapshot`** (PARA hot block + user profile).
3. **Rules** — **`RulesCache.load`** → **`format_rules_block`** (GraphQL-backed in **`rules/graphql.py`**).
4. **Skills** — **`build_skills_system_block`** (manifest, eligibility, session permission, token budget).
5. **Prompt** — **`PromptBuilder.build`** (mode, channel, personality, context files, memory, skills XML, rules, optional user/system hints).
6. **Messages** — Initial **`ProviderMessage`** list: `system` + `user`.
7. **Tools** — **`list_openai_tools`**, filtered by session permission, channel, and route.
8. **Provider** — **`_provider_for_request`**: **`ProviderRouter`** (Gemini / OpenRouter) when at least one of **`GENAI_API_KEY`**, **`GOOGLE_API_KEY`**, **`OPENROUTER_API_KEY`** is set; **`EchoProvider`** only when **`DEV_ECHO_MODE=echo`** (used in tests via conftest autouse); missing keys without echo raises **`RuntimeError`** at **`AgentRunner()`** construction.
9. **Tool context** — **`ToolContext`** + **`set_tool_context`** (user, session, bearer token, progress sink, memory root, route metadata).
10. **Telemetry** — Optional **Langfuse** wrappers on provider and tool registry; **`agent_run_observation`**.
11. **`run_turn_loop`** (see below).
12. **Progress** — `usage`, `task_progress_summary`.
13. **Response** — **`ChatResponseV3`** + metadata; plan mode may attach **`FileComponent`**; **`capture_event`** for product analytics.

### `run_turn_loop` (`agent/loop.py`)

- **Bound** — Up to **`MAX_ITERATIONS`** (24) LLM↔tool rounds.
- Each iteration: **`ProgressSink.cot_step`** (active, with a random spinner label from `const.SPINNER_VERBS` — e.g. `"Cogitating…"`) → **`provider.complete(messages, tools_enabled, effort)`** → append assistant message (optionally with **`tool_calls`**).
- If finish reason is **`tool_calls`** and tools are enabled: **`ToolRegistry.execute`** per call → append **`role=tool`** messages; repeat.
- Otherwise return **`LoopResult`** (final text, full transcript, iteration count, finish reason, provider metadata).
- Exceeding max iterations yields finish reason **`length`**.

**Summary:** One composed system prompt plus user text goes in; the loop runs **multi-step LLM ↔ tool** until stop or cap; final assistant text (and optional **`FileComponent`**s) comes out.

## Major subsystems

| Area | Location | Notes |
|------|-----------|--------|
| **Providers** | `providers/router.py`, `gemini.py`, `openrouter.py`, `schema_normalize.py` | Effort routing, fallbacks, schema normalization for tool definitions. |
| **Tools** | `tools/registry.py`, `tools/base.py`, `fmp.py`, `yld.py`, `search/*`, `graphql.py`, … | Permissions via **`ToolContext`**; tools emit **`tool_start` / `tool_done`** CoT steps. |
| **Routes (automation)** | `routes/registry.py`, `routes/dispatch.py`, `routes/actions_*.py`, `spaces_*.py`, `memory_*.py`, `llm_council.py` | Route string → async handler + **`RouteContext`**. |
| **PARA memory** | `memory/para.py`, `loader.py`, `writer.py`, `bridges/*`, `merge.py` | File layout under **`MEMORY_ROOT`**; bridges may call GraphQL (some surfaces stubbed). |
| **Skills** | `skills/*`, repo-level `skills/bootstrap_manifest.yaml` | Discovery roots, eligibility, mandatory prompt block. |
| **Rules** | `rules/cache.py`, `rules/graphql.py`, `rules/format.py` | Cached rules snapshot from supergraph. |
| **Hooks** | `hooks/runner.py`, `compact.py`, `collapse.py`, `auto_dream.py`, `skill_review.py` | Post-response; configured via env. |
| **Council** | `council/*` | Multi-model panel + chairman; invoked from council route. |
| **Telemetry** | `telemetry/*` | Sentry, PostHog, Langfuse; redaction helpers. |
| **CLI** | `cli/chat.py`, `__main__.py` | Local chat; can pass through JWT for tools. |
| **Gateway** | `gateway/*` | WhatsApp (optional **neonize**), Discord stub, HTTP forwarder to **`/v3/agent/question`**. |
| **Usage** | `usage/capture.py` | Records usage in a GraphQL-oriented shape for downstream persistence. |
| **Deprecated v2** | `deprecated/v2/*` | Legacy stack including **`gql`**-based GraphQL clients — **not** wired as the default v3 runner path. |

## GraphQL in v3

v3 uses a thin **`tools/graphql.py`** client (HTTP POST to **`{GATEWAY_URL}/graphql`** with Bearer token) plus query strings in **`rules/graphql.py`** and selected **`memory/bridges`**. Rich per-domain clients from ai-master live under **`deprecated/v2/api/`** only.

## Non-goals (behavioral)

- **No token-level streaming** of assistant content; progress uses **CoT / task / usage**-style events (e.g. over WebSocket).
- v2 HTTP surface is not mounted; compatibility is schema-level where needed.

## Related docs

- **`DESIGN.md`** — Product and environment intent.
- **`plans/00-ai-harness-master-plan.md`** — Phased implementation plan at repo root.
