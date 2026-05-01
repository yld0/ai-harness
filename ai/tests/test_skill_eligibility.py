"""Eligibility: bins, env, and permission gating."""

from pathlib import Path

import pytest

from ai.skills.eligibility import is_eligible
from ai.skills.registry import build_skill_index


def test_eligibility_hidden_missing_bin(tmp_path: Path) -> None:
    skill_dir = tmp_path / "references-skills" / "bin-test"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n" "name: bin-test\ndescription: needs fake binary\n" "bin:\n  - __nonexistent_binary_zz_qq__\n" "---\n\n# X\n",
        encoding="utf-8",
    )
    found = build_skill_index(tmp_path)
    assert not any(e.name == "bin-test" for e in found)


def test_eligibility_shown_when_bin_exists(tmp_path: Path) -> None:
    skill_dir = tmp_path / "references-skills" / "ok-bin"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n" "name: ok-bin\ndescription: needs python (always on PATH in tests)\n" "bin:\n  - python3\n" "---\n\n# X\n",
        encoding="utf-8",
    )
    found = {e.name: e for e in build_skill_index(tmp_path)}
    assert "ok-bin" in found


def test_readonly_hides_write_skill(tmp_path: Path) -> None:
    skill_dir = tmp_path / "references-skills" / "wskill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n" "name: wskill\ndescription: needs workspace write\n" "tools:\n  - WorkspaceWrite\n" "---\n\n# X\n",
        encoding="utf-8",
    )
    assert not any(e.name == "wskill" for e in build_skill_index(tmp_path, session_permission="ReadOnly"))
    assert any(e.name == "wskill" for e in build_skill_index(tmp_path, session_permission="ReadWrite"))


def test_is_eligible_respects_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SKILLTEST_TOKEN", raising=False)
    assert not is_eligible(
        {"name": "x", "description": "y", "env": ["SKILLTEST_TOKEN"]},
        permission="ReadWrite",
    )
    monkeypatch.setenv("SKILLTEST_TOKEN", "1")
    assert is_eligible(
        {"name": "x", "description": "y", "env": ["SKILLTEST_TOKEN"]},
        permission="ReadWrite",
    )
