"""Typed schemas for PARA memory files."""

from datetime import date
from enum import Enum
from typing import Any, Literal

from pydantic import Field, field_validator

from ai.schemas._base import CamelBaseModel


class Validity(str, Enum):
    EVERGREEN = "evergreen"
    EXPIRES = "expires"
    POINT_IN_TIME = "point_in_time"


class FactStatus(str, Enum):
    ACTIVE = "active"
    HISTORICAL = "historical"
    SUPERSEDED = "superseded"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Direction(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class SourceType(str, Enum):
    AGENT_ANALYSIS = "agent_analysis"
    USER_INPUT = "user_input"
    API_DATA = "api_data"
    EARNINGS_CALL = "earnings_call"
    ANALYST_REPORT = "analyst_report"
    NEWS = "news"


FactCategory = Literal[
    "valuation",
    "price_snapshot",
    "sentiment",
    "analyst_rating",
    "thesis",
    "macro",
    "earnings",
    "guidance",
    "catalyst",
    "structural",
]

CATEGORY_HALF_LIFE_DAYS: dict[str, int] = {
    "price_snapshot": 3,
    "valuation": 7,
    "sentiment": 14,
    "analyst_rating": 30,
    "thesis": 90,
    "macro": 30,
}


class MemoryFact(CamelBaseModel):
    id: str
    fact: str
    category: FactCategory = "structural"
    validity: Validity = Validity.EVERGREEN
    half_life_days: int | None = None
    expires: date | None = None
    confidence: Confidence = Confidence.MEDIUM
    direction: Direction | None = None
    source_type: SourceType = SourceType.AGENT_ANALYSIS
    source_ref: str | None = None
    recorded_at: date
    timestamp: date | None = None
    status: FactStatus = FactStatus.ACTIVE
    superseded_by: str | None = None
    superseded_by_text: str | None = None
    transitioned_at: date | None = None
    related_entities: list[str] = Field(default_factory=list)
    last_accessed: date | None = None
    access_count: int = 0
    score: float | None = None

    @field_validator("timestamp", mode="before")
    @classmethod
    def default_timestamp(cls, value: Any) -> Any:
        return value

    def model_post_init(self, __context: Any) -> None:
        if self.timestamp is None:
            object.__setattr__(self, "timestamp", self.recorded_at)
        if self.validity == Validity.POINT_IN_TIME and self.half_life_days is None:
            object.__setattr__(
                self,
                "half_life_days",
                CATEGORY_HALF_LIFE_DAYS.get(self.category, 14),
            )

    def to_yaml_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=False, exclude_none=True)


class HotMemorySnapshot(CamelBaseModel):
    user_id: str
    session_id: str
    content: str
    user_profile: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
