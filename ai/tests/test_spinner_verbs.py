"""Tests for spinner verb helpers (_truncate_query, choose_spinner_verb_bucket)."""

import hashlib
from unittest.mock import patch

from ai.const import SPINNER_VERBS
from ai.utils.spinner_verbs import (
    _truncate_query,
    choose_spinner_verb_bucket,
)

# ── _truncate_query ───────────────────────────────────────────────────────────


def test_truncate_query_first_sentence() -> None:
    """Stops at the first period."""
    assert _truncate_query("hello world. more stuff") == "hello world"


def test_truncate_query_newline() -> None:
    """Stops at the first newline."""
    assert _truncate_query("first line\nsecond line") == "first line"


def test_truncate_query_strips_whitespace() -> None:
    """Leading/trailing whitespace is removed."""
    assert _truncate_query("  padded  ") == "padded"


def test_truncate_query_no_delimiter() -> None:
    """Returns the full string when no period or newline present."""
    assert _truncate_query("heartbeat-extract low") == "heartbeat-extract low"


def test_truncate_query_empty_first_segment() -> None:
    """Falls back to full stripped input when splitting yields empty first part."""
    assert _truncate_query(".starts with dot") == ".starts with dot"


# ── choose_spinner_verb_bucket ────────────────────────────────────────────────


def test_choose_bucket_no_context_uses_random() -> None:
    """Without context, uses random.choice like the docstring fallback."""
    with patch("ai.utils.spinner_verbs.random.choice", return_value="Cogitating"):
        assert choose_spinner_verb_bucket(None) == "Cogitating…"


def test_choose_bucket_no_context_pick_from_verbs() -> None:
    """Unpatched random still draws from SPINNER_VERBS."""
    verb = choose_spinner_verb_bucket(None).rstrip("…")
    assert verb in SPINNER_VERBS


def test_choose_bucket_same_context_stable() -> None:
    """Same *context* always yields the same label (hash of first 40 chars)."""
    ctx = "analyzing the portfolio diversification strategy"
    a = choose_spinner_verb_bucket(ctx)
    b = choose_spinner_verb_bucket(ctx)
    assert a == b


def test_choose_bucket_finance_core_pool() -> None:
    """Finance-related words map into the finance core verb pool."""
    ctx = "running dcf valuation on this name"
    label = choose_spinner_verb_bucket(ctx)
    assert label == choose_spinner_verb_bucket(ctx)
    assert label.rstrip("…") in {"Allocating", "Concentrating", "Deliberating"}


def test_choose_bucket_math_pool() -> None:
    """Math / calculation stems hit the math bucket."""
    ctx = "statistics and formula work"
    label = choose_spinner_verb_bucket(ctx)
    assert label == choose_spinner_verb_bucket(ctx)
    assert label.rstrip("…") in {"Calculating", "Computing", "Crunching", "Quantumizing"}


def test_choose_bucket_no_match_uses_global_list() -> None:
    """Unmatched alphanumeric words use SPINNER_VERBS with the same md5 index."""
    ctx = "xyz qwerty nondescript fluff"
    key = ctx[:40].encode()
    idx = int(hashlib.md5(key, usedforsecurity=False).hexdigest(), 16)
    expected = f"{SPINNER_VERBS[idx % len(SPINNER_VERBS)]}…"
    assert choose_spinner_verb_bucket(ctx) == expected


def test_choose_bucket_ends_with_ellipsis() -> None:
    """Every return ends with U+2026."""
    assert choose_spinner_verb_bucket("code review and deploy").endswith("…")


def test_choose_bucket_matches_alpha_bucket_before_finance_when_first() -> None:
    """'alpha' is in the alpha/moat bucket, which precedes unrelated buckets."""
    ctx = "re-search, paused: alpha!"
    label = choose_spinner_verb_bucket(ctx)
    assert label.rstrip("…") in {"Alphaing", "Betaing", "FatPitching", "Flywheeling", "Moating"}


# ── choose_spinner_verb (vector path — currently disabled in spinner_verbs) ────
#
# import asyncio
# from unittest.mock import AsyncMock, MagicMock, patch
#
# import httpx
#
# from ai.const import SPINNER_VERBS, _SPINNER_VERBS_SET
# from ai.utils.spinner_verbs import choose_spinner_verb
#
#
# def _run(coro):
#     """ Helper to run an async coroutine in tests. """
#     return asyncio.run(coro)
#
#
# def test_no_context_returns_random() -> None:
#     """ Without context, returns a random verb from the list. """
#     with patch("ai.utils.spinner_verbs.random.choice", return_value="Cogitating"):
#         result = _run(choose_spinner_verb.__wrapped__(None))
#     assert result == "Cogitating…"
#
#
# def test_no_context_verb_is_from_list() -> None:
#     """ The random fallback always picks from SPINNER_VERBS. """
#     result = _run(choose_spinner_verb.__wrapped__(None))
#     verb = result.rstrip("…")
#     assert verb in SPINNER_VERBS
#
#
# def test_with_context_returns_vector_match() -> None:
#     """ When vector search succeeds, returns the matched verb. """
#     fake_doc = ({"verb": "Calculating"}, 0.95)
#
#     with (
#         patch("ai.utils.spinner_verbs._embed_query", new_callable=AsyncMock, return_value=[0.1] * 128),
#         patch("ai.utils.spinner_verbs.vector_search", new_callable=AsyncMock, return_value=[fake_doc]),
#         patch("ai.utils.spinner_verbs._get_collection", return_value=MagicMock()),
#     ):
#         result = _run(choose_spinner_verb.__wrapped__("financial analysis"))
#     assert result == "Calculating…"
#
#
# def test_embedding_failure_falls_back() -> None:
#     """ On embedding API failure, falls back to random. """
#     with (
#         patch("ai.utils.spinner_verbs._embed_query", new_callable=AsyncMock, side_effect=httpx.HTTPError("boom")),
#         patch("ai.utils.spinner_verbs.random.choice", return_value="Musing"),
#     ):
#         result = _run(choose_spinner_verb.__wrapped__("financial analysis"))
#     assert result == "Musing…"
#
#
# def test_mongo_failure_falls_back() -> None:
#     """ On MongoDB failure, falls back to random. """
#     with (
#         patch("ai.utils.spinner_verbs._embed_query", new_callable=AsyncMock, return_value=[0.1] * 128),
#         patch("ai.utils.spinner_verbs._get_collection", return_value=MagicMock()),
#         patch("ai.utils.spinner_verbs.vector_search", new_callable=AsyncMock, side_effect=Exception("mongo down")),
#         patch("ai.utils.spinner_verbs.random.choice", return_value="Pondering"),
#     ):
#         result = _run(choose_spinner_verb.__wrapped__("financial analysis"))
#     assert result == "Pondering…"
#
#
# def test_unknown_verb_falls_back() -> None:
#     """ If vector search returns a verb not in SPINNER_VERBS, falls back. """
#     fake_doc = ({"verb": "UnknownVerb"}, 0.8)
#
#     with (
#         patch("ai.utils.spinner_verbs._embed_query", new_callable=AsyncMock, return_value=[0.1] * 128),
#         patch("ai.utils.spinner_verbs.vector_search", new_callable=AsyncMock, return_value=[fake_doc]),
#         patch("ai.utils.spinner_verbs._get_collection", return_value=MagicMock()),
#         patch("ai.utils.spinner_verbs.random.choice", return_value="Brewing"),
#     ):
#         result = _run(choose_spinner_verb.__wrapped__("some context"))
#     assert result == "Brewing…"
#
#
# def test_empty_vector_results_falls_back() -> None:
#     """ When vector search returns no results, falls back to random. """
#     with (
#         patch("ai.utils.spinner_verbs._embed_query", new_callable=AsyncMock, return_value=[0.1] * 128),
#         patch("ai.utils.spinner_verbs.vector_search", new_callable=AsyncMock, return_value=[]),
#         patch("ai.utils.spinner_verbs._get_collection", return_value=MagicMock()),
#         patch("ai.utils.spinner_verbs.random.choice", return_value="Stewing"),
#     ):
#         result = _run(choose_spinner_verb.__wrapped__("some context"))
#     assert result == "Stewing…"
#
#
# def test_result_always_ends_with_ellipsis() -> None:
#     """ Every return value ends with the ellipsis character. """
#     result = _run(choose_spinner_verb.__wrapped__(None))
#     assert result.endswith("…")
