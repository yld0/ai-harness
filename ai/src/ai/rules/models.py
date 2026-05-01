"""Domain models for the rules system.

Defines ``Rule`` and ``RulesSnapshot`` — used by the cache, formatter,
and bridge modules.  These are pure data containers with no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=True)
class Rule:
    id: str
    instructions: str
    name: Optional[str] = None
    always_apply: bool = True


@dataclass(frozen=True)
class RulesSnapshot:
    always_apply: list[Rule] = field(default_factory=list)
    manual: list[Rule] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_empty(self) -> bool:
        return not self.always_apply and not self.manual
