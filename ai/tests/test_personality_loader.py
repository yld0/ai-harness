"""Tests for PersonalityLoader: front-matter parsing, shadowing, missing-name errors."""

from __future__ import annotations

import pytest
from pathlib import Path

from ai.agent.personalities.loader import (
    Personality,
    PersonalityLoader,
    PersonalityNotFound,
    _parse_personality_file,
)

# ──────────────────────────── File parser ─────────────────────────────────── #


class TestParsePersonalityFile:
    def test_full_frontmatter(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\nname: mypersona\ndescription: A test.\neffort_hint: medium\n---\n\nBe helpful.")
        p = _parse_personality_file(f)
        assert p.name == "mypersona"
        assert p.description == "A test."
        assert p.effort_hint == "medium"
        assert p.prompt == "Be helpful."

    def test_name_fallback_to_stem(self, tmp_path):
        f = tmp_path / "fallback.md"
        f.write_text("---\ndescription: no name field\n---\n\nBody text.")
        p = _parse_personality_file(f)
        assert p.name == "fallback"

    def test_no_frontmatter(self, tmp_path):
        f = tmp_path / "plain.md"
        f.write_text("Just a plain body with no front matter.")
        p = _parse_personality_file(f)
        assert p.name == "plain"
        assert "plain body" in p.prompt

    def test_missing_effort_hint_is_none(self, tmp_path):
        f = tmp_path / "nohint.md"
        f.write_text("---\nname: nohint\ndescription: Test.\n---\n\nBody.")
        p = _parse_personality_file(f)
        assert p.effort_hint is None

    def test_empty_description(self, tmp_path):
        f = tmp_path / "empty.md"
        f.write_text("---\nname: empty\n---\n\nBody.")
        p = _parse_personality_file(f)
        assert p.description == ""

    def test_name_lowercased(self, tmp_path):
        f = tmp_path / "upper.md"
        f.write_text("---\nname: CamelCase\n---\n\nBody.")
        p = _parse_personality_file(f)
        assert p.name == "camelcase"

    def test_malformed_yaml_uses_stem(self, tmp_path):
        f = tmp_path / "broken.md"
        f.write_text("---\n{not: valid: yaml: [\n---\nBody.")
        # Should not raise; name falls back to stem
        p = _parse_personality_file(f)
        assert p.name == "broken"


# ──────────────────────────── Loader: discovery ───────────────────────────── #


class TestPersonalityLoaderDiscovery:
    def _make_loader(self, tmp_path: Path) -> PersonalityLoader:
        return PersonalityLoader(repo_root=tmp_path)

    def _add_personality(self, root: Path, name: str, description: str = "", body: str = "Body.") -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / f"{name}.md").write_text(f"---\nname: {name}\ndescription: {description}\n---\n\n{body}")

    def test_list_empty_when_no_root(self, tmp_path):
        loader = self._make_loader(tmp_path)
        # No personalities/ dir under tmp_path
        assert loader.list() == []

    def test_list_discovers_from_repo_root(self, tmp_path):
        self._add_personality(tmp_path / "personalities", "alpha", "Alpha desc")
        loader = self._make_loader(tmp_path)
        names = [p.name for p in loader.list()]
        assert "alpha" in names

    def test_list_sorted_by_name(self, tmp_path):
        pers_dir = tmp_path / "personalities"
        for name in ("zzz", "aaa", "mmm"):
            self._add_personality(pers_dir, name)
        loader = self._make_loader(tmp_path)
        names = [p.name for p in loader.list()]
        assert names == sorted(names)

    def test_get_returns_personality(self, tmp_path):
        self._add_personality(tmp_path / "personalities", "beta", "Beta desc", "Be brief.")
        loader = self._make_loader(tmp_path)
        p = loader.get("beta")
        assert p.name == "beta"
        assert p.description == "Beta desc"
        assert "brief" in p.prompt

    def test_get_case_insensitive(self, tmp_path):
        self._add_personality(tmp_path / "personalities", "gamma")
        loader = self._make_loader(tmp_path)
        p = loader.get("GAMMA")
        assert p.name == "gamma"

    def test_get_raises_not_found(self, tmp_path):
        loader = self._make_loader(tmp_path)
        with pytest.raises(PersonalityNotFound, match="ghost"):
            loader.get("ghost")

    def test_not_found_message_includes_available(self, tmp_path):
        self._add_personality(tmp_path / "personalities", "delta")
        loader = self._make_loader(tmp_path)
        with pytest.raises(PersonalityNotFound, match="delta"):
            loader.get("nothere")


# ──────────────────────────── Loader: shadowing ──────────────────────────── #


class TestPersonalityLoaderShadowing:
    """Higher-priority roots must override lower-priority ones for same name."""

    def test_workspace_shadows_repo(self, tmp_path):
        repo_root = tmp_path / "repo"
        workspace = tmp_path / "workspace"

        # Repo version
        pers_repo = repo_root / "personalities"
        pers_repo.mkdir(parents=True)
        (pers_repo / "shared.md").write_text("---\nname: shared\ndescription: Repo version.\n---\n\nRepo body.")

        # Workspace version (higher priority)
        pers_ws = workspace / "personalities"
        pers_ws.mkdir(parents=True)
        (pers_ws / "shared.md").write_text("---\nname: shared\ndescription: Workspace version.\n---\n\nWorkspace body.")

        loader = PersonalityLoader(workspace_root=workspace, repo_root=repo_root)
        p = loader.get("shared")
        assert p.description == "Workspace version."
        assert "Workspace body" in p.prompt

    def test_repo_only_when_no_workspace(self, tmp_path):
        pers_dir = tmp_path / "personalities"
        pers_dir.mkdir()
        (pers_dir / "solo.md").write_text("---\nname: solo\ndescription: Only in repo.\n---\n\nSolo body.")
        loader = PersonalityLoader(repo_root=tmp_path)
        p = loader.get("solo")
        assert "Solo body" in p.prompt

    def test_list_deduplicates_shadowed_name(self, tmp_path):
        """Same personality name from two roots appears only once in list()."""
        repo_root = tmp_path / "repo"
        workspace = tmp_path / "workspace"
        for pers_dir in (repo_root / "personalities", workspace / "personalities"):
            pers_dir.mkdir(parents=True)
            (pers_dir / "dup.md").write_text(f"---\nname: dup\ndescription: {pers_dir.parent.name}.\n---\n\nBody.")
        loader = PersonalityLoader(workspace_root=workspace, repo_root=repo_root)
        personalities = loader.list()
        dup_count = sum(1 for p in personalities if p.name == "dup")
        assert dup_count == 1

    def test_shadowed_value_is_highest_priority(self, tmp_path):
        """When repo + workspace both define 'dup', workspace wins."""
        repo_root = tmp_path / "repo"
        workspace = tmp_path / "workspace"
        (repo_root / "personalities").mkdir(parents=True)
        (repo_root / "personalities" / "dup.md").write_text("---\nname: dup\ndescription: low.\n---\n\nLow.")
        (workspace / "personalities").mkdir(parents=True)
        (workspace / "personalities" / "dup.md").write_text("---\nname: dup\ndescription: high.\n---\n\nHigh.")
        loader = PersonalityLoader(workspace_root=workspace, repo_root=repo_root)
        p = loader.get("dup")
        assert p.description == "high."


# ──────────────────────────── Bundled defaults ────────────────────────────── #


class TestBundledPersonalities:
    """Vendored personality files shipped with the repo must parse correctly."""

    def test_bundled_personalities_load(self):
        """The ai/ project must ship default, codereviewer, and criticise personalities."""
        # Loader defaults to the ai/ project root (parents[4] from loader.py)
        loader = PersonalityLoader()
        names = {p.name for p in loader.list()}
        for expected in ("default", "codereviewer", "criticise"):
            assert expected in names, f"Bundled personality '{expected}' not found"

    def test_bundled_default_has_description(self):
        loader = PersonalityLoader()
        p = loader.get("default")
        assert p.description
        assert p.prompt

    def test_bundled_codereviewer_effort_hint(self):
        loader = PersonalityLoader()
        p = loader.get("codereviewer")
        assert p.effort_hint == "medium"

    def test_bundled_criticise_effort_hint(self):
        loader = PersonalityLoader()
        p = loader.get("criticise")
        assert p.effort_hint == "high"
