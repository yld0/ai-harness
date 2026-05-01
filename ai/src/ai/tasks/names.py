"""Background job / UI identifiers (parity with v2 WebSocket `job_id` strings)."""

from __future__ import annotations

from enum import StrEnum


class BackgroundJobId(StrEnum):
    """Stable ids used in v2 for spaces + compaction flows (wire compatibility)."""

    SPACES_DISCOVER = "spaces-discover"
    SPACES_KNOWLEDGE_BASE = "spaces-knowledge-base-sources-refresh"
    SPACES_SUMMARY = "spaces-summary"
    SPACES_COMPACT = "spaces-compact"
    SPACES_YOUTUBE = "spaces-youtube-summary"
