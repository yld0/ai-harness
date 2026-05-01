"""Skill discovery, eligibility, and prompt index (Phase 5)."""

from ai.skills.registry import (
    build_skills_system_block,
    build_skill_index,
    skill_discovery_roots,
)
from ai.skills.types import SkillIndexEntry, SkillsBuildResult

__all__ = [
    "SkillIndexEntry",
    "SkillsBuildResult",
    "build_skill_index",
    "build_skills_system_block",
    "skill_discovery_roots",
]
