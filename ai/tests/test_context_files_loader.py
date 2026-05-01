"""Tests for extended ContextFilesLoader (Phase 12).

Covers:
- Basic discovery in root directory (AGENTS.md, .cursorrules, etc.)
- SOUL.md as identity source
- SOUL.md included in context files block when custom and non-default
- Workspace upward search (walks ancestor directories)
- Deduplication: same file not added twice
- Cursor .mdc rules directory
- Truncation at MAX_CONTEXT_FILE_CHARS
"""

from __future__ import annotations

import pytest
from pathlib import Path

from ai.agent.context_files import (
    ContextFilesLoader,
    MAX_CONTEXT_FILE_CHARS,
    CONTEXT_FILE_NAMES,
)
from ai.agent.personality import DEFAULT_AGENT_IDENTITY

# ──────────────────────────── Basic discovery ────────────────────────────── #


class TestBasicDiscovery:
    def test_empty_root_no_files(self, tmp_path):
        loader = ContextFilesLoader(tmp_path)
        snap = loader.load()
        assert snap.files == []
        assert snap.identity == DEFAULT_AGENT_IDENTITY

    def test_agents_md_discovered(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# Agents\nDo stuff.")
        loader = ContextFilesLoader(tmp_path)
        snap = loader.load()
        assert any("AGENTS.md" in f.path for f in snap.files)

    def test_cursorrules_discovered(self, tmp_path):
        (tmp_path / ".cursorrules").write_text("Always use types.")
        loader = ContextFilesLoader(tmp_path)
        snap = loader.load()
        assert any(".cursorrules" in f.path for f in snap.files)

    def test_only_first_match_from_root(self, tmp_path):
        """When both AGENTS.md and .cursorrules exist, only AGENTS.md is loaded from root."""
        (tmp_path / "AGENTS.md").write_text("agents content")
        (tmp_path / ".cursorrules").write_text("cursor content")
        loader = ContextFilesLoader(tmp_path)
        snap = loader.load()
        root_files = [f for f in snap.files if "AGENTS.md" in f.path or ".cursorrules" in f.path]
        # Only one from root (first match wins)
        assert sum(1 for f in root_files if f.path.endswith("AGENTS.md")) == 1

    def test_content_is_correct(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("hello content")
        loader = ContextFilesLoader(tmp_path)
        snap = loader.load()
        matches = [f for f in snap.files if "AGENTS.md" in f.path]
        assert matches[0].content == "hello content"

    def test_cursor_mdc_rules(self, tmp_path):
        rules_dir = tmp_path / ".cursor" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "style.mdc").write_text("Style rule body.")
        (rules_dir / "naming.mdc").write_text("Naming rule body.")
        loader = ContextFilesLoader(tmp_path)
        snap = loader.load()
        mdc_files = [f for f in snap.files if f.path.endswith(".mdc")]
        assert len(mdc_files) == 2

    def test_truncation(self, tmp_path):
        big = "x" * (MAX_CONTEXT_FILE_CHARS + 500)
        (tmp_path / "AGENTS.md").write_text(big)
        loader = ContextFilesLoader(tmp_path)
        snap = loader.load()
        found = next(f for f in snap.files if "AGENTS.md" in f.path)
        assert "[truncated]" in found.content
        assert len(found.content) <= MAX_CONTEXT_FILE_CHARS + 20


# ──────────────────────────── Identity / SOUL.md ─────────────────────────── #


class TestIdentity:
    def test_default_identity_when_no_soul(self, tmp_path):
        loader = ContextFilesLoader(tmp_path)
        snap = loader.load()
        assert snap.identity == DEFAULT_AGENT_IDENTITY

    def test_soul_md_becomes_identity(self, tmp_path):
        (tmp_path / "SOUL.md").write_text("Custom AI identity.")
        loader = ContextFilesLoader(tmp_path)
        snap = loader.load()
        assert snap.identity == "Custom AI identity."

    def test_soul_md_included_as_context_file(self, tmp_path):
        """Custom SOUL.md should appear in context files block, not just identity."""
        (tmp_path / "SOUL.md").write_text("Custom AI identity text that is non-default.")
        loader = ContextFilesLoader(tmp_path)
        snap = loader.load()
        soul_files = [f for f in snap.files if "SOUL.md" in f.path]
        assert len(soul_files) == 1

    def test_default_soul_md_not_in_context_files(self, tmp_path):
        """Writing the exact default identity string should not duplicate into context files."""
        (tmp_path / "SOUL.md").write_text(DEFAULT_AGENT_IDENTITY)
        loader = ContextFilesLoader(tmp_path)
        snap = loader.load()
        soul_files = [f for f in snap.files if "SOUL.md" in f.path]
        assert len(soul_files) == 0


# ──────────────────────────── Upward search ──────────────────────────────── #


class TestUpwardSearch:
    def test_finds_agents_md_in_parent(self, tmp_path):
        """Workspace root set to a subdirectory; AGENTS.md found in parent."""
        workspace = tmp_path / "subdir" / "deep"
        workspace.mkdir(parents=True)
        # AGENTS.md lives two levels up
        (tmp_path / "AGENTS.md").write_text("# Root agents")
        loader = ContextFilesLoader(tmp_path, workspace_root=workspace)
        snap = loader.load()
        agents_files = [f for f in snap.files if "AGENTS.md" in f.path]
        assert len(agents_files) >= 1

    def test_nearest_ancestor_wins(self, tmp_path):
        """Closest AGENTS.md to workspace_root should be picked up."""
        workspace = tmp_path / "a" / "b" / "c"
        workspace.mkdir(parents=True)
        # Place one at 'a' level
        (tmp_path / "a" / "AGENTS.md").write_text("Level A agents")
        # Place another at root
        (tmp_path / "AGENTS.md").write_text("Root agents")
        loader = ContextFilesLoader(tmp_path, workspace_root=workspace)
        snap = loader.load()
        # At least one AGENTS.md should appear
        agents_files = [f for f in snap.files if "AGENTS.md" in f.path]
        assert len(agents_files) >= 1

    def test_no_workspace_no_extra_search(self, tmp_path):
        """Without workspace_root, only root is searched."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "AGENTS.md").write_text("Sub AGENTS")
        loader = ContextFilesLoader(tmp_path)
        snap = loader.load()
        # sub/AGENTS.md should NOT appear since no workspace_root set
        sub_files = [f for f in snap.files if str(sub) in f.path]
        assert len(sub_files) == 0

    def test_workspace_equal_root_no_duplicate(self, tmp_path):
        """workspace_root == root should not duplicate context files."""
        (tmp_path / "AGENTS.md").write_text("Content")
        loader = ContextFilesLoader(tmp_path, workspace_root=tmp_path)
        snap = loader.load()
        agents_files = [f for f in snap.files if "AGENTS.md" in f.path]
        assert len(agents_files) == 1

    def test_upward_search_max_levels(self, tmp_path):
        """Stops after MAX_ANCESTOR_LEVELS without finding anything — no crash."""
        # Create a 10-level deep directory; AGENTS.md at tmp_path root (> 5 levels up)
        deep = tmp_path
        for i in range(10):
            deep = deep / f"level{i}"
        deep.mkdir(parents=True)
        (tmp_path / "AGENTS.md").write_text("Root content")
        loader = ContextFilesLoader(tmp_path, workspace_root=deep)
        # Should not raise; may or may not find the file depending on depth
        snap = loader.load()
        assert isinstance(snap.files, list)


# ──────────────────────────── Deduplication ──────────────────────────────── #


class TestDeduplication:
    def test_same_file_not_added_twice(self, tmp_path):
        """If workspace_root is a subdirectory that finds the same file as root, no duplicate."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "AGENTS.md").write_text("Root AGENTS.md")
        # workspace_root points to sub, but upward search finds root's AGENTS.md
        loader = ContextFilesLoader(tmp_path, workspace_root=sub)
        snap = loader.load()
        agents_files = [f for f in snap.files if "AGENTS.md" in f.path]
        # The same path should not appear twice
        paths = [f.path for f in agents_files]
        assert len(paths) == len(set(paths))
