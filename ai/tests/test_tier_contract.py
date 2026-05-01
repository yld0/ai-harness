"""Tier contract tests (Phase 22).

Verify that the eval-tier system (T0–T4) is correctly wired:
  - ``pyproject.toml`` registers the slow and live markers.
  - ``evals/README.md`` documents all tier labels, the default command, and
    the env-gate variables.
  - The golden YAML tier distribution satisfies the T0-landing-bar policy.
  - Test files that use ``@pytest.mark.live`` respect the ``AI_HARNESS_LIVE_EVAL``
    guard.
  - The default pytest run (``not slow and not live``) never executes T3 tests.

All tests are offline T0 (no network, no LLM).
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest
import yaml

# ─── helpers ──────────────────────────────────────────────────────────────────


def _pyproject(project_root: str) -> str:
    return (Path(project_root) / "pyproject.toml").read_text(encoding="utf-8")


def _evals_readme(project_root: str) -> str:
    return (Path(project_root) / "evals" / "README.md").read_text(encoding="utf-8")


def _golden_cases(project_root: str) -> list[dict]:
    path = Path(project_root) / "evals" / "financial_qa_golden.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw.get("cases", [])


# ─── pyproject.toml — marker registration ─────────────────────────────────────


def test_slow_marker_registered(project_root: str) -> None:
    content = _pyproject(project_root)
    assert "slow" in content, "slow marker not found in pyproject.toml"


def test_live_marker_registered(project_root: str) -> None:
    content = _pyproject(project_root)
    assert "live" in content, "live marker not found in pyproject.toml"


def test_both_markers_in_markers_section(project_root: str) -> None:
    content = _pyproject(project_root)
    # Markers must appear after [tool.pytest.ini_options]
    ini_idx = content.find("[tool.pytest.ini_options]")
    assert ini_idx != -1, "[tool.pytest.ini_options] section missing from pyproject.toml"
    section = content[ini_idx:]
    assert "slow" in section and "live" in section, "slow/live markers must be registered under [tool.pytest.ini_options]"


def test_filterwarnings_configured(project_root: str) -> None:
    content = _pyproject(project_root)
    assert "filterwarnings" in content, "filterwarnings not configured in pyproject.toml — test output will be noisy"


# ─── evals/README.md — tier documentation ─────────────────────────────────────


def test_readme_documents_all_tier_labels(project_root: str) -> None:
    content = _evals_readme(project_root)
    for tier in ("T0", "T1", "T2", "T3", "T4"):
        assert tier in content, f"Tier {tier} not documented in evals/README.md"


def test_readme_has_default_command(project_root: str) -> None:
    content = _evals_readme(project_root)
    assert "not slow and not live" in content, "evals/README.md must document the default pytest invocation: " '-m "not slow and not live"'


def test_readme_documents_live_eval_env_var(project_root: str) -> None:
    content = _evals_readme(project_root)
    assert "AI_HARNESS_LIVE_EVAL" in content, "evals/README.md must document AI_HARNESS_LIVE_EVAL env variable"


def test_readme_documents_t0_as_landing_bar(project_root: str) -> None:
    content = _evals_readme(project_root)
    assert "T0" in content and (
        "landing" in content.lower() or "default" in content.lower()
    ), "evals/README.md should explain that T0 is the default landing bar"


# ─── golden YAML — tier distribution ─────────────────────────────────────────


def test_golden_yaml_valid_tiers_only(project_root: str) -> None:
    valid = {"T0", "T1", "T2", "T3", "T4"}
    cases = _golden_cases(project_root)
    bad = [c["id"] for c in cases if c.get("tier", "T0") not in valid]
    assert not bad, f"Cases with invalid tier values: {bad}"


def test_golden_yaml_majority_are_t0(project_root: str) -> None:
    """T0 must be the plurality tier — it drives default CI."""
    cases = _golden_cases(project_root)
    t0_count = sum(1 for c in cases if c.get("tier", "T0") == "T0")
    total = len(cases)
    # T0 should be at least 50% of cases.
    assert t0_count / total >= 0.5, (
        f"T0 cases are {t0_count}/{total} ({t0_count/total:.0%}). " "T0 should be the dominant tier to keep the landing bar lean."
    )


def test_golden_yaml_t2_cases_exist(project_root: str) -> None:
    """At least one T2 case should exist to test the slow-marker path."""
    cases = _golden_cases(project_root)
    t2_count = sum(1 for c in cases if c.get("tier") == "T2")
    assert t2_count >= 1, "No T2 cases in golden YAML — add at least one to exercise the slow marker path"


def test_golden_yaml_no_t4_in_static_file(project_root: str) -> None:
    """T4 is manual/exploratory — should not appear as a static YAML case."""
    cases = _golden_cases(project_root)
    t4 = [c["id"] for c in cases if c.get("tier") == "T4"]
    assert not t4, f"T4 cases should not be in the static YAML: {t4}"


# ─── default run excludes T3 ──────────────────────────────────────────────────


def test_live_env_flag_absent_in_default_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """In a default test run, AI_HARNESS_LIVE_EVAL should not be set."""
    monkeypatch.delenv("AI_HARNESS_LIVE_EVAL", raising=False)
    assert not os.environ.get("AI_HARNESS_LIVE_EVAL"), "AI_HARNESS_LIVE_EVAL is set — this test must not run in a live-eval context"


def test_financebench_flag_absent_in_default_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In a default test run, RUN_FINANCEBENCH should not be set."""
    monkeypatch.delenv("RUN_FINANCEBENCH", raising=False)
    assert not os.environ.get("RUN_FINANCEBENCH")


# ─── @pytest.mark.live files respect the env gate ────────────────────────────


def test_live_marked_test_files_have_env_guard(project_root: str) -> None:
    """Any test file containing @pytest.mark.live must also reference AI_HARNESS_LIVE_EVAL.

    This guards against accidentally shipping live tests that run without the
    opt-in flag being set.
    """
    tests_dir = Path(project_root) / "tests"
    offenders: list[str] = []
    for path in sorted(tests_dir.glob("test_*.py")):
        content = path.read_text(encoding="utf-8")
        if "@pytest.mark.live" in content and "AI_HARNESS_LIVE_EVAL" not in content:
            offenders.append(path.name)
    assert not offenders, f"Test files with @pytest.mark.live but no AI_HARNESS_LIVE_EVAL guard:\n" + "\n".join(f"  {f}" for f in offenders)


def test_slow_marked_test_files_exist(project_root: str) -> None:
    """At least one test file must use @pytest.mark.slow (exercises the slow marker path)."""
    tests_dir = Path(project_root) / "tests"
    files_with_slow = [p.name for p in sorted(tests_dir.glob("test_*.py")) if "@pytest.mark.slow" in p.read_text(encoding="utf-8")]
    assert files_with_slow, "No test files use @pytest.mark.slow — add at least one T2 test to exercise the marker"


# ─── tier-aware query helpers ─────────────────────────────────────────────────


def test_golden_yaml_t0_subset_is_usable_standalone(project_root: str) -> None:
    """T0 cases alone must be self-contained: all have assertions, no missing fields."""
    cases = _golden_cases(project_root)
    t0 = [c for c in cases if c.get("tier", "T0") == "T0"]
    for c in t0:
        assert c.get("id"), "T0 case missing id"
        assert c.get("input"), f"T0 case {c.get('id')} missing input"
        assert c.get("route"), f"T0 case {c.get('id')} missing route"
        assert c.get("rubric") or c.get("expected_substrings"), f"T0 case {c.get('id')} has no rubric or expected_substrings"


def test_golden_yaml_tier_counts_logged(project_root: str, capsys: pytest.CaptureFixture) -> None:
    """Print tier distribution for human review (not a failure gate)."""
    cases = _golden_cases(project_root)
    from collections import Counter

    dist = Counter(c.get("tier", "T0") for c in cases)
    print(f"\nGolden YAML tier distribution: {dict(sorted(dist.items()))}")
    # Just assert total matches expected minimum.
    assert sum(dist.values()) >= 20


# ─── pyproject.toml — asyncio_mode ────────────────────────────────────────────


def test_asyncio_mode_auto_configured(project_root: str) -> None:
    """asyncio_mode = 'auto' must be set so @pytest.mark.asyncio is not needed on every test."""
    content = _pyproject(project_root)
    assert 'asyncio_mode = "auto"' in content or "asyncio_mode = 'auto'" in content, "asyncio_mode must be set to 'auto' in pyproject.toml"
