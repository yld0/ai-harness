"""Validate ``evals/financial_qa_golden.yaml`` structure (T0 gate)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class GoldenCase(BaseModel):
    id: str
    input: str
    route: str
    mode: str
    expected_capabilities: list[str] = Field(default_factory=list)
    required_tools_or_sources: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)
    rubric: str | None = None
    expected_substrings: list[str] | None = None
    tier: str = "T0"
    tags: list[str] = Field(default_factory=list)

    @field_validator("tier")
    @classmethod
    def tier_known(cls, v: str) -> str:
        if v not in {"T0", "T1", "T2", "T3", "T4"}:
            raise ValueError(f"unknown tier: {v}")
        return v

    def model_post_init(self, __context: object) -> None:
        if not self.rubric and not self.expected_substrings:
            raise ValueError(
                f"case {self.id!r} needs rubric or expected_substrings",
            )


class GoldenFile(BaseModel):
    version: int = 1
    cases: list[GoldenCase]


def _golden_path(project_root: str) -> Path:
    return Path(project_root) / "evals" / "financial_qa_golden.yaml"


def test_financial_golden_yaml_loads(project_root: str) -> None:
    path = _golden_path(project_root)
    assert path.is_file(), f"missing {path}"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    model = GoldenFile.model_validate(raw)
    assert len(model.cases) >= 20


def test_financial_golden_categories_span_routes(project_root: str) -> None:
    path = _golden_path(project_root)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    model = GoldenFile.model_validate(raw)
    routes = {c.route for c in model.cases}
    assert len(routes) >= 4


def test_financial_golden_t0_cases_form_landing_bar(project_root: str) -> None:
    """T0 cases must be the dominant tier — they are the default-CI landing bar."""
    path = _golden_path(project_root)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    model = GoldenFile.model_validate(raw)
    t0_cases = [c for c in model.cases if c.tier == "T0"]
    assert len(t0_cases) >= 15, f"Expected ≥15 T0 cases to form the landing bar; got {len(t0_cases)}"


def test_financial_golden_t0_cases_all_have_assertions(project_root: str) -> None:
    """Every T0 case must have a deterministic assertion (rubric or expected_substrings)."""
    path = _golden_path(project_root)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    model = GoldenFile.model_validate(raw)
    bad = [c.id for c in model.cases if c.tier == "T0" and not c.rubric and not c.expected_substrings]
    assert not bad, f"T0 cases missing assertions: {bad}"


def test_financial_golden_no_t3_cases_in_static_yaml(project_root: str) -> None:
    """Static golden YAML must not contain T3 cases (T3 = live eval, not a static contract)."""
    path = _golden_path(project_root)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    model = GoldenFile.model_validate(raw)
    t3_cases = [c.id for c in model.cases if c.tier == "T3"]
    assert not t3_cases, f"T3 cases must not be in the static YAML (they require live LLM): {t3_cases}"


def test_financial_golden_all_cases_have_tags(project_root: str) -> None:
    """Every case must have at least one tag for filtering and reporting."""
    path = _golden_path(project_root)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    model = GoldenFile.model_validate(raw)
    untagged = [c.id for c in model.cases if not c.tags]
    assert not untagged, f"Cases missing tags: {untagged}"
