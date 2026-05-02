"""FinanceBench optional full-eval track (Phase 21).

Marked ``@pytest.mark.slow`` — **not** run in default CI.

Requires:
    - ``RUN_FINANCEBENCH=1`` environment variable (explicit opt-in)
    - ``FINANCEBENCH_DATA_DIR`` pointing at a local FinanceBench data directory
      that contains ``financebench_open_source.jsonl``

Mode: **B** (tool/API-only agent, no PDF RAG). The agent calls harness tools
(FMP, web search, etc.) to answer financial questions without reading the
bundled PDFs. Scores are expected to be **lower** than the paper's RAG
pipeline; the caveat is documented in ``evals/financebench/README.md``.

To run locally::

    export RUN_FINANCEBENCH=1
    export FINANCEBENCH_DATA_DIR=/path/to/financebench/data
    cd ai && uv run pytest tests/test_financebench_eval_optional.py -m slow -s

Langfuse tracing (optional): set ``LANGFUSE_PUBLIC_KEY`` / ``LANGFUSE_SECRET_KEY``
and spans are automatically emitted from the harness runner.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from evals.financebench.load_dataset import data_dir_from_env, load_eval_dataset
from evals.financebench.metrics import aggregate_scores, score_row


def _check_prerequisites() -> tuple[bool, str]:
    if not os.environ.get("RUN_FINANCEBENCH"):
        return False, "RUN_FINANCEBENCH not set; skipping FinanceBench eval"
    data_dir = data_dir_from_env()
    if data_dir is None:
        return False, "FINANCEBENCH_DATA_DIR not set or directory not found"
    return True, ""


# ─── gate test ────────────────────────────────────────────────────────────────


@pytest.mark.slow
def test_financebench_data_available():
    """Verify that the data directory and questions file are present."""
    ok, reason = _check_prerequisites()
    if not ok:
        pytest.skip(reason)

    data_dir = data_dir_from_env()
    assert data_dir is not None
    questions_file = data_dir / "financebench_open_source.jsonl"
    assert questions_file.is_file(), f"Questions file not found: {questions_file}\n" "Acquire FinanceBench data: see evals/financebench/README.md"


# ─── loader integration ───────────────────────────────────────────────────────


@pytest.mark.slow
def test_financebench_loader_integration():
    """Load the full (or sampled) dataset and verify structural properties."""
    ok, reason = _check_prerequisites()
    if not ok:
        pytest.skip(reason)

    data_dir = data_dir_from_env()
    eval_rows = load_eval_dataset(data_dir, max_rows=50)

    assert len(eval_rows) > 0, "No eval rows loaded — check FINANCEBENCH_DATA_DIR"
    for row in eval_rows:
        assert row.id, f"Row missing id: {row}"
        assert row.input, f"Row {row.id} has empty question"
        assert row.expected_answer, f"Row {row.id} has empty answer"


@pytest.mark.slow
def test_financebench_question_types_present():
    """At least three distinct question types should be present in the open sample."""
    ok, reason = _check_prerequisites()
    if not ok:
        pytest.skip(reason)

    data_dir = data_dir_from_env()
    eval_rows = load_eval_dataset(data_dir)
    types = {r.question_type for r in eval_rows if r.question_type}
    assert len(types) >= 3, f"Expected ≥3 question types, got: {types}"


# ─── baseline scorer (Mode B: null/stub predictions) ─────────────────────────


@pytest.mark.slow
def test_financebench_metrics_baseline_scores():
    """Run stub predictions ('I don't know') to confirm the metrics pipeline works end-to-end.

    This is a **sanity check**, not a real eval: exact match will be ~0.
    Replace ``_predict()`` with a real agent call for a proper score.
    """
    ok, reason = _check_prerequisites()
    if not ok:
        pytest.skip(reason)

    data_dir = data_dir_from_env()
    eval_rows = load_eval_dataset(data_dir, max_rows=10)

    scored = [score_row(r, "I don't know") for r in eval_rows]
    summary = aggregate_scores(scored)

    # Structural checks — not score thresholds (stub predictions will score 0).
    assert summary["n"] == len(eval_rows)
    assert 0.0 <= summary["exact_match"] <= 1.0
    assert 0.0 <= summary["token_f1_mean"] <= 1.0
    assert isinstance(summary["by_question_type"], dict)

    # Print summary for local inspection.
    print(f"\nFinanceBench baseline (stub) summary: {summary}")


# ─── per-type breakdown ───────────────────────────────────────────────────────


@pytest.mark.slow
def test_financebench_aggregate_has_buckets():
    """Aggregate output must include per-question-type breakdown keys."""
    ok, reason = _check_prerequisites()
    if not ok:
        pytest.skip(reason)

    data_dir = data_dir_from_env()
    eval_rows = load_eval_dataset(data_dir, max_rows=20)

    # Use gold as prediction → expect near-perfect EM for sanity.
    scored = [score_row(r, r.expected_answer) for r in eval_rows]
    summary = aggregate_scores(scored)

    assert summary["exact_match"] > 0.8, f"Expected high EM when predicting gold; got {summary['exact_match']}. " "Check normalize_answer for regressions."
    for bucket_name, bucket in summary["by_question_type"].items():
        assert "n" in bucket
        assert "exact_match" in bucket
        assert "token_f1_mean" in bucket
