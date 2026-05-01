"""Tests for spaces route handlers: discover, kb-refresh, summary, compact, youtube-summary."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml

from ai.memory.para import ParaMemoryLayout
from ai.memory.schemas import FactStatus, MemoryFact, Validity
from ai.memory.writer import MemoryWriter
from ai.routes.context import RouteContext


def _make_fact(fid: str, *, validity: Validity = Validity.EVERGREEN) -> MemoryFact:
    return MemoryFact(id=fid, fact=f"fact-{fid}", validity=validity, recorded_at=date.today())


def _make_ctx(
    tmp_path: Path,
    input_data: dict | None = None,
    llm_return: str = "Generated content.",
) -> RouteContext:
    layout = ParaMemoryLayout(tmp_path)
    layout.ensure_user_layout("u1")
    return RouteContext(
        user_id="u1",
        request=None,  # type: ignore[arg-type]
        bearer_token=None,
        input=input_data or {},
        layout=layout,
        writer=MemoryWriter(layout),
        progress=AsyncMock(),
        call_llm=AsyncMock(return_value=llm_return),
    )


def _seed_space(ctx: RouteContext, space_id: str, sources: list[dict] | None = None) -> Path:
    """Ensure space layout and optionally write sources.yaml."""
    ctx.writer.ensure_entity_layout(ctx.user_id, kind="spaces", entity_id=space_id)
    space_dir = ctx.layout.entity_dir(ctx.user_id, "spaces", space_id)
    if sources is not None:
        sources_path = space_dir / "sources.yaml"
        sources_path.write_text(yaml.safe_dump(sources), encoding="utf-8")
    return space_dir


# ─── spaces-discover ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discover_missing_space_id(tmp_path):
    from ai.routes.spaces_discover import run

    ctx = _make_ctx(tmp_path, {})
    result = await run(ctx)
    assert result.ok is False
    assert result.error == "missing_input"


@pytest.mark.asyncio
async def test_discover_returns_llm_suggestions(tmp_path):
    from ai.routes.spaces_discover import run

    ctx = _make_ctx(
        tmp_path,
        {"space_id": "ai-research"},
        llm_return="1. ArXiv – daily\n2. Hacker News – daily",
    )
    _seed_space(ctx, "ai-research")
    result = await run(ctx)
    assert result.ok is True
    assert "ArXiv" in result.text


@pytest.mark.asyncio
async def test_discover_topic_in_prompt(tmp_path):
    from ai.routes.spaces_discover import run

    ctx = _make_ctx(tmp_path, {"space_id": "climate", "topic": "renewable energy"})
    _seed_space(ctx, "climate")
    await run(ctx)
    prompt = ctx.call_llm.call_args[0][0]
    assert "renewable energy" in prompt


@pytest.mark.asyncio
async def test_discover_error(tmp_path):
    from ai.routes.spaces_discover import run

    ctx = _make_ctx(tmp_path, {"space_id": "bio"})
    ctx.call_llm.side_effect = RuntimeError("llm down")
    _seed_space(ctx, "bio")
    result = await run(ctx)
    assert result.ok is False
    assert result.error == "llm_error"


# ─── spaces-knowledge-base-sources-refresh ────────────────────────────────────


@pytest.mark.asyncio
async def test_kb_refresh_missing_space_id(tmp_path):
    from ai.routes.spaces_kb_refresh import run

    ctx = _make_ctx(tmp_path, {})
    result = await run(ctx)
    assert result.ok is False
    assert result.error == "missing_input"


@pytest.mark.asyncio
async def test_kb_refresh_no_sources(tmp_path):
    from ai.routes.spaces_kb_refresh import run

    ctx = _make_ctx(tmp_path, {"space_id": "empty-space"})
    _seed_space(ctx, "empty-space", sources=[])
    result = await run(ctx)
    assert result.ok is True
    assert result.metadata["refreshed"] == 0


@pytest.mark.asyncio
async def test_kb_refresh_updates_last_fetched(tmp_path):
    from ai.routes.spaces_kb_refresh import run

    old_date = "2020-01-01T00:00:00+00:00"
    sources = [
        {
            "url": "https://example.com/feed",
            "timingValidity": "daily",
            "last_fetched": old_date,
        }
    ]
    ctx = _make_ctx(tmp_path, {"space_id": "news-space"})
    space_dir = _seed_space(ctx, "news-space", sources=sources)

    result = await run(ctx)
    assert result.ok is True
    assert result.metadata["refreshed"] == 1

    updated_sources = yaml.safe_load((space_dir / "sources.yaml").read_text())
    assert updated_sources[0]["last_fetched"] != old_date


@pytest.mark.asyncio
async def test_kb_refresh_writes_knowledge_base_md(tmp_path):
    from ai.routes.spaces_kb_refresh import run

    sources = [
        {
            "url": "https://example.com",
            "timingValidity": "weekly",
            "last_fetched": "2020-01-01T00:00:00Z",
        }
    ]
    ctx = _make_ctx(tmp_path, {"space_id": "wiki"}, llm_return="# Wiki KB\n\nContent here.")
    space_dir = _seed_space(ctx, "wiki", sources=sources)

    result = await run(ctx)
    assert result.ok is True
    kb_path = space_dir / "knowledge-base.md"
    assert kb_path.is_file()
    assert "Wiki KB" in kb_path.read_text()


@pytest.mark.asyncio
async def test_kb_refresh_force_refreshes_all(tmp_path):
    from ai.routes.spaces_kb_refresh import run

    now = datetime.now(timezone.utc).isoformat()
    sources = [
        {"url": "https://a.com", "timingValidity": "evergreen", "last_fetched": now},
        {"url": "https://b.com", "timingValidity": "evergreen", "last_fetched": now},
    ]
    ctx = _make_ctx(tmp_path, {"space_id": "force-test", "force": True})
    _seed_space(ctx, "force-test", sources=sources)

    result = await run(ctx)
    assert result.metadata["refreshed"] == 2


# ─── spaces-summary ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_spaces_summary_missing_space_id(tmp_path):
    from ai.routes.spaces_summary import run

    ctx = _make_ctx(tmp_path, {})
    result = await run(ctx)
    assert result.ok is False
    assert result.error == "missing_input"


@pytest.mark.asyncio
async def test_spaces_summary_invalid_style(tmp_path):
    from ai.routes.spaces_summary import run

    ctx = _make_ctx(tmp_path, {"space_id": "s1", "style": "invalid_style"})
    _seed_space(ctx, "s1")
    result = await run(ctx)
    assert result.ok is False
    assert result.error == "invalid_style"


@pytest.mark.asyncio
@pytest.mark.parametrize("style", ["report", "deep_report", "key_takeaways", "blog_post", "tldr", "summary"])
async def test_spaces_summary_valid_styles(tmp_path, style):
    from ai.routes.spaces_summary import run

    ctx = _make_ctx(tmp_path, {"space_id": "s1", "style": style}, llm_return=f"Report for {style}")
    _seed_space(ctx, "s1")
    result = await run(ctx)
    assert result.ok is True
    assert result.metadata["style"] == style


@pytest.mark.asyncio
async def test_spaces_summary_persists_report_file(tmp_path):
    from ai.routes.spaces_summary import run

    ctx = _make_ctx(tmp_path, {"space_id": "finspace", "style": "tldr"}, llm_return="TLDR content")
    space_dir = _seed_space(ctx, "finspace")
    result = await run(ctx)
    assert result.ok is True
    report_path = Path(result.metadata["report_path"])
    assert report_path.is_file()
    assert "TLDR content" in report_path.read_text()
    assert "finspace/reports/tldr" in str(report_path)


# ─── spaces-compact ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_spaces_compact_missing_space_id(tmp_path):
    from ai.routes.spaces_compact import run

    ctx = _make_ctx(tmp_path, {})
    result = await run(ctx)
    assert result.ok is False
    assert result.error == "missing_input"


@pytest.mark.asyncio
async def test_spaces_compact_creates_summary(tmp_path):
    from ai.routes.spaces_compact import run

    ctx = _make_ctx(tmp_path, {"space_id": "space1"})
    fact = _make_fact("f1", validity=Validity.EVERGREEN)
    ctx.writer.write_fact("u1", kind="spaces", entity_id="space1", fact=fact)
    result = await run(ctx)
    assert result.ok is True
    space_dir = ctx.layout.entity_dir("u1", "spaces", "space1")
    assert (space_dir / "summary.md").is_file()


@pytest.mark.asyncio
async def test_spaces_compact_updates_kb(tmp_path):
    from ai.routes.spaces_compact import run

    ctx = _make_ctx(tmp_path, {"space_id": "space2"}, llm_return="Refreshed KB content")
    fact = _make_fact("f1", validity=Validity.EVERGREEN)
    ctx.writer.write_fact("u1", kind="spaces", entity_id="space2", fact=fact)
    result = await run(ctx)
    assert result.ok is True
    space_dir = ctx.layout.entity_dir("u1", "spaces", "space2")
    kb_path = space_dir / "knowledge-base.md"
    assert kb_path.is_file()
    assert "Refreshed KB" in kb_path.read_text()


# ─── spaces-youtube-summary ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_youtube_missing_space_id(tmp_path):
    from ai.routes.spaces_youtube_summary import run

    ctx = _make_ctx(tmp_path, {"transcript": "hello world"})
    result = await run(ctx)
    assert result.ok is False
    assert result.error == "missing_input"


@pytest.mark.asyncio
async def test_youtube_no_transcript(tmp_path):
    from ai.routes.spaces_youtube_summary import run

    ctx = _make_ctx(tmp_path, {"space_id": "yt-space", "url": "https://youtu.be/abc"})
    result = await run(ctx)
    assert result.ok is False
    assert result.error == "no_transcript"


@pytest.mark.asyncio
async def test_youtube_summary_ok(tmp_path):
    from ai.routes.spaces_youtube_summary import run

    transcript = "This video explains transformers in detail..."
    ctx = _make_ctx(
        tmp_path,
        {"space_id": "ml", "transcript": transcript, "title": "Transformers 101"},
        llm_return="Key takeaways: 1. Attention is all you need.",
    )
    _seed_space(ctx, "ml")
    result = await run(ctx)
    assert result.ok is True
    assert "Attention" in result.text


@pytest.mark.asyncio
async def test_youtube_summary_appends_to_kb(tmp_path):
    from ai.routes.spaces_youtube_summary import run

    ctx = _make_ctx(
        tmp_path,
        {"space_id": "ml2", "transcript": "Deep dive on RLHF...", "title": "RLHF Talk"},
        llm_return="RLHF summary.",
    )
    space_dir = _seed_space(ctx, "ml2")
    (space_dir / "knowledge-base.md").write_text("# ML2\n\nExisting content.\n", encoding="utf-8")

    result = await run(ctx)
    assert result.ok is True
    kb_text = (space_dir / "knowledge-base.md").read_text()
    assert "Existing content" in kb_text
    assert "RLHF" in kb_text
