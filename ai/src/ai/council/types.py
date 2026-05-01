"""Council data types — no v2 schema dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CouncilOpinion:
    """One panelist's response to the query."""

    model: str
    text: str
    failed: bool = False
    error: Optional[str] = None


@dataclass
class CouncilRanking:
    """One panelist's ranking of the anonymous opinions."""

    model: str
    raw: str  # full ranking text
    parsed: list[str]  # ordered labels, e.g. ["Response A", "Response C"]
    failed: bool = False


@dataclass
class CouncilResult:
    """Final output from the full council run."""

    final_text: str
    opinions: list[CouncilOpinion] = field(default_factory=list)
    rankings: list[CouncilRanking] = field(default_factory=list)
    aggregate_rankings: list[dict[str, Any]] = field(default_factory=list)
    judge_model: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
