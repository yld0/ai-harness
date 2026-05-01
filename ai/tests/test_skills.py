"""Golden and integration tests for skills index formatting."""

from pathlib import Path

import pytest

from ai.skills.prompt import build_skills_prompt, mandatory_block
from ai.skills.registry import (
    _parse_front_matter_text,
    build_skill_index,
    build_skills_system_block,
)
from ai.skills.types import SkillIndexEntry


def test_mandatory_block_mentions_read_tool() -> None:
    text = mandatory_block("read_file")
    assert "`read_file`" in text
    assert "Skills (mandatory)" in text
    assert "scan" in text.lower()


def test_golden_ordering_and_xml_shape() -> None:
    a = Path("/w/z/SKILL.md")
    b = Path("/w/a/SKILL.md")
    e2 = SkillIndexEntry(name="Beta", description="Second", skill_md_path=a, source="t", frontmatter={})
    e1 = SkillIndexEntry(name="alpha", description="First", skill_md_path=b, source="t", frontmatter={})
    out = build_skills_prompt([e2, e1], read_tool_name="read_file", max_chars=50_000)
    assert out.compact is False
    # Sorted by name: alpha, Beta
    i_alpha = out.prompt_text.index("alpha")
    i_beta = out.prompt_text.index("Beta")
    assert i_alpha < i_beta
    assert "<available_skills>" in out.prompt_text
    assert "<name>alpha</name>" in out.prompt_text
    assert "<description>First</description>" in out.prompt_text
    assert "</available_skills>" in out.prompt_text
    assert "## Skills (mandatory)" in out.prompt_text


def test_parse_front_matter_multiline() -> None:
    sample = "---\n" "name: test-skill\ndescription: 'Hello world'\n" "bin:\n  - mytool\n" "---\n" "\n# Body\n"
    fm, body = _parse_front_matter_text(sample)
    assert fm.get("name") == "test-skill"
    assert "Body" in body


@pytest.fixture
def mini_repo_with_skills(tmp_path: Path) -> Path:
    (tmp_path / "references-skills" / "a-skill").mkdir(parents=True)
    (tmp_path / "references-skills" / "a-skill" / "SKILL.md").write_text(
        "---\n" "name: a-skill\ndescription: From references\n" "---\n\n# A\n",
        encoding="utf-8",
    )
    (tmp_path / "skills" / "a-skill").mkdir(parents=True)
    (tmp_path / "skills" / "a-skill" / "SKILL.md").write_text(
        "---\n" "name: a-skill\ndescription: Overridden in workspace\n" "requires_write: true\n" "---\n\n# W\n",
        encoding="utf-8",
    )
    return tmp_path


def test_workspace_shadows_references(mini_repo_with_skills: Path) -> None:
    found = {e.name: e for e in build_skill_index(mini_repo_with_skills)}
    assert "a-skill" in found
    assert "Overridden" in found["a-skill"].description
    assert found["a-skill"].source == "workspace"


def test_build_system_block_includes_bootstrap_repo(tmp_path: Path) -> None:
    (tmp_path / "references-skills" / "para-memory-files").mkdir(parents=True)
    (tmp_path / "references-skills" / "para-memory-files" / "SKILL.md").write_text(
        "---\n" "name: para-memory-files\ndescription: Test skill for index\n" "---\n\n# X\n",
        encoding="utf-8",
    )
    r = build_skills_system_block(tmp_path, max_prompt_chars=100_000)
    assert "para-memory-files" in r.prompt_text
    assert "Test skill for index" in r.prompt_text
