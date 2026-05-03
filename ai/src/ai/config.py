from dataclasses import dataclass
from typing import List, Optional

from shared.envutil.config import item, load, register


@register
@dataclass
class Config:
    AUTH_SECRETPHRASE: str  # Dont want to default
    SECRET_KEY: str  # Dont want to default
    PORT: int = item(default=8005, description="Port to run the service on")
    RELOAD: bool = item(default=False, description="Enable auto-reload")
    GATEWAY_URL: str = item(default="http://66.135.26.112/api/graphql", description="Gateway URL")
    WS_MAX_AUTH_FAILURES: int = item(default=5, description="Maximum consecutive websocket auth failures")
    WS_IDLE_TIMEOUT_SECONDS: float = item(default=1800.0, description="WebSocket idle timeout in seconds")


# NOTE: So can import scripts without having to pass in the config
@register
@dataclass
class LoggingConfig:
    LOG_LEVEL: str = "INFO"
    LOG_COMPONENT: str = "ai"


@register
@dataclass
class MongoConfig:
    MONGO_URL: str = item(default="localhost", description="MongoDB URI")
    MONGO_PORT: int = item(default=27017, description="MongoDB Port")
    MONGO_DB = "yld0"
    FMP_MONGO_DB = "fmp_v2"
    AUTH_MONGO_DB = "auth"


@register
@dataclass
class RedisConfig:
    REDIS_HOST: str = item(default="127.0.0.1", description="Redis host")
    REDIS_PORT: int = item(default=6379, description="Redis port")
    REDIS_DB: str = item(default="0", description="Redis logical DB index")
    REDIS_USERNAME: str = item(default="", description="Redis username (optional)")
    REDIS_PASSWORD: str = item(default="", description="Redis password (optional)")

    def url(self, db: Optional[str] = None) -> str:
        auth = f"{self.REDIS_USERNAME}:{self.REDIS_PASSWORD}@" if self.REDIS_USERNAME and self.REDIS_PASSWORD else ""
        db = db or self.REDIS_DB
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{db}"


@register
@dataclass
class URLMetaConfig:
    """urlmeta.org credentials for link preview metadata (optional)."""

    URLMETA_API_KEY: str = item(default="", description="URL Meta API Basic token")


@register
@dataclass
class TelemetryConfig:
    """Sentry, PostHog, and Langfuse (see DESIGN.md — Telemetry)."""

    SENTRY_DSN: str = item(default="", description="Sentry DSN; empty disables Sentry")
    POSTHOG_API_KEY: str = item(default="", description="PostHog project API key")
    POSTHOG_HOST: str = item(
        default="https://app.posthog.com",
        description="PostHog ingest host",
    )
    LANGFUSE_PUBLIC_KEY: str = item(default="", description="Langfuse public key")
    LANGFUSE_SECRET_KEY: str = item(default="", description="Langfuse secret key")
    LANGFUSE_HOST: str = item(
        default="https://cloud.langfuse.com",
        description="Langfuse API host",
    )
    TELEMETRY_REDACT_PROMPTS: str = item(
        default="1",
        description="When 1/true, redact large prompt/tool payloads in telemetry",
    )
    TELEMETRY_REDACT_TOOL_ARGS: str = item(
        default="1",
        description="When 1/true, redact tool argument values (names/keys kept)",
    )
    TELEMETRY_SAMPLE_RATE: str = item(
        default="1.0",
        description="Sentry traces sample rate 0.0–1.0",
    )


@register
@dataclass
class MCPConfig:
    """MCP (Model Context Protocol) tool servers — optional.

    When ``MCP_SERVERS`` is empty, MCP integration stays off and no heavy SDK
    imports run. Value is parsed by :func:`ai.mcp.config.parse_mcp_servers_env`
    (JSON object or CSV ``name:url`` shorthand).
    """

    MCP_SERVERS: str = item(
        default="",
        description=(
            "MCP servers: JSON object of name → url or full objects, or CSV "
            "name:url pairs. Example: fmp:http://localhost:8080/sse or "
            '\'{"fmp": {"url": "http://localhost:8080/sse"}}\''
        ),
    )


@register
@dataclass
class HealthConfig:
    """Optional liveness dependency probe settings for ``/healthz``."""

    HEALTHZ_PROBE_DEPS: bool = item(
        default=False,
        description="When True, attempt lightweight HTTP reachability checks against configured dependency URLs",
    )
    GRAPHQL_HEALTH_URL: str = item(
        default="http://66.135.26.112/api/graphql",  # TODO: Expose actual health endpoint
        description="URL for GraphQL service health probe",
    )
    GEMINI_HEALTH_URL: str = item(
        default="",
        description="URL for Gemini health probe; empty disables the probe",
    )
    OPENROUTER_HEALTH_URL: str = item(
        default="https://openrouter.ai/healthz",
        description="URL for OpenRouter health probe",
    )
    FMP_HEALTH_URL: str = item(
        default="https://financialmodelingprep.com",
        description="URL for Financial Modeling Prep health probe",
    )


@register
@dataclass
class AutomationConfig:
    """Automation-run settings."""

    AUTOMATION_REPLAY_TTL_SECONDS: int = item(
        default=3600,
        description="TTL in seconds for in-process idempotency replay cache keyed by (user_id, automation_run_id)",
    )


@register
@dataclass
class CouncilConfig:
    """LLM Council configuration."""

    OPENROUTER_API_KEY: str = item(default="", description="OpenRouter API key for council models")
    COUNCIL_MODELS: List[str] = item(
        default_factory=lambda: [
            "openai/gpt-5.1",
            "google/gemini-3-pro-preview",
            "anthropic/claude-sonnet-4.5",
            "x-ai/grok-4",
            "moonshotai/kimi-k2-thinking",
        ],
        description="Council member models (OpenRouter identifiers)",
    )
    CHAIRMAN_MODEL: str = item(
        default="google/gemini-3-flash-preview",
        description="Chairman model for final synthesis",
    )
    OPENROUTER_API_URL: str = item(
        default="https://openrouter.ai/api/v1/chat/completions",
        description="OpenRouter API endpoint",
    )


@register
@dataclass
class HookConfig:
    """Per-process hook flags and thresholds for post-response processing."""

    AI_HOOKS_ENABLED: List[str] = item(default_factory=list, description="Enabled hooks (CSV of hook names)")
    AI_COMPACT_SOFT_CHARS: int = item(default=12_000, description="Soft compaction threshold in chars")
    AI_COLLAPSE_HARD_CHARS: int = item(default=48_000, description="Hard collapse threshold in chars")
    AI_COLLAPSE_KEEP_PAIRS: int = item(default=3, description="Recent user/assistant pairs to keep after collapse")
    AI_EXTRACT_MEMORIES_EVERY_N: int = item(
        default=5,
        description="Append PARA daily note / light extract every N turns (0 disables extract_memories hook)",
    )
    AI_AUTO_DREAM_ENABLED: bool = item(
        default=False,
        description="When True, gated periodic memory consolidation (auto_dream hook) may run after other gates pass",
    )
    AI_AUTO_DREAM_MIN_HOURS: int = item(
        default=24,
        description="Minimum hours since last consolidation (lock mtime) before auto-dream may run",
    )
    AI_AUTO_DREAM_MIN_SESSIONS: int = item(
        default=5,
        description="Minimum distinct daily-note files touched since last consolidation (excluding today) to run dream",
    )
    AI_AUTO_DREAM_SCAN_THROTTLE_S: int = item(
        default=600,
        description="Per-user throttle between session scans when time gate passes (seconds)",
    )
    AI_AUTO_DREAM_RECENT_DAILY_NOTES: int = item(
        default=7,
        description="Number of recent calendar daily notes to include in dream prompt",
    )
    AI_AUTO_DREAM_MODEL: str = item(
        default="",
        description="OpenRouter or Gemini model id for dream consolidation; empty uses default low-effort router model",
    )
    AI_POST_HOOK_TIMEOUT_S: float = item(default=30.0, description="Total post-hook budget in seconds")
    AI_SKILL_REVIEW_THRESHOLD: int = item(default=10, description="Tool-call count that triggers a background skill review")
    AI_SKILL_REVIEW_MODEL: str = item(
        default="deepseek/deepseek-v4-pro",
        description="OpenRouter or Gemini model id for autonomous skill review proposals",
    )


@register
@dataclass
class CliConfig:
    """Standalone CLI environment configuration."""

    CLI_USER_ID: str = item(default="cli-user", description="Default user id for standalone CLI sessions")
    CLI_BEARER_TOKEN: str = item(default="", description="Bearer token forwarded from the CLI to GraphQL-backed tools")
    CLI_MEMORY_ROOT: str = item(default="./memory", description="Path to the PARA memory root directory for CLI sessions")
    CLI_MODEL: str = item(default="", description="Default model override for standalone CLI sessions")


@register
@dataclass
class AgentConfig:
    """AgentRunner environment configuration."""

    DEV_ECHO_MODE: bool = item(
        default=False,
        description="Set to True for offline stub responses",
    )
    GENAI_API_KEY: str = item(default="", description="Gemini API key")
    GOOGLE_API_KEY: str = item(default="", description="Google API key (alternative to GENAI_API_KEY)")
    OPENROUTER_API_KEY: str = item(default="", description="OpenRouter API key")
    MEMORY_ROOT: str = item(default="./memory", description="Path to the PARA memory root directory")
    AI_READ_TOOL_NAME: str = item(default="read_file", description="Override the read tool name used in skills prompts")
    AI_SKILLS_INDEX_MAX_CHARS: int = item(
        default=30_000,
        description="Override max chars for skills index prompt",
    )
    AI_FALLBACK_MODELS: List[str] = item(
        default_factory=list,
        description="Comma-separated fallback model IDs for the provider router (envutil list)",
    )
    EMBEDDING_MODEL: str = item(
        default="perplexity/pplx-embed-v1-0.6b",
        description="OpenRouter embedding model ID",
    )
    SPINNER_VERBS_COLLECTION: str = item(
        default="spinnerverbs",
        description="MongoDB collection for spinner verb embeddings",
    )


hook_config = load(HookConfig)
mongo_config = load(MongoConfig)
redis_config = load(RedisConfig)
urlmeta_config = load(URLMetaConfig)
telemetry_config = load(TelemetryConfig)
mcp_config = load(MCPConfig)
health_config = load(HealthConfig)
automation_config = load(AutomationConfig)
council_config = load(CouncilConfig)
cli_config = load(CliConfig)
log_config = load(LoggingConfig)
agent_config = load(AgentConfig)
agent_config.AI_FALLBACK_MODELS = (
    ["deepseek/deepseek-v4-flash", "anthropic/claude-sonnet-4.6"] if not agent_config.AI_FALLBACK_MODELS else agent_config.AI_FALLBACK_MODELS
)
config = load(Config)
