"""FinanceBench evaluation metrics (Phase 21).

String-level correctness metrics for financial QA:

- :func:`normalize_answer` — canonical text form for comparison.
- :func:`exact_match` — normalized exact match (primary gate).
- :func:`token_f1` — token-level F1 (precision × recall harmonic mean), useful
  for numeric + free-form answers where wording varies.
- :func:`score_row` — run all metrics for one row; returns a ``dict``.
- :func:`aggregate_scores` — per-type bucketing + overall summary.
"""

from __future__ import annotations

import re
import string
from collections import Counter
from typing import Any

from evals.financebench.schema import EvalRow

# ── Text normalisation ─────────────────────────────────────────────────────────

_CURRENCY_RE = re.compile(r"\$\s*")
_PERCENT_RE = re.compile(r"%")
_COMMA_RE = re.compile(r"(?<=\d),(?=\d)")  # remove thousand-separator commas only
_WHITESPACE_RE = re.compile(r"\s+")
_PUNC_TABLE = str.maketrans("", "", string.punctuation)


def normalize_answer(text: str) -> str:
    """Normalise a gold or predicted answer string for comparison.

    Steps:
    1. Strip leading/trailing whitespace; lowercase.
    2. Remove ``$`` currency symbols.
    3. Remove ``%`` (comparisons treat "10%" and "10" as equal after stripping).
    4. Remove thousand-separator commas inside numbers (``1,234`` → ``1234``).
    5. Strip remaining punctuation.
    6. Collapse internal whitespace.
    """
    text = text.strip().lower()
    text = _CURRENCY_RE.sub("", text)
    text = _PERCENT_RE.sub("", text)
    text = _COMMA_RE.sub("", text)
    text = text.translate(_PUNC_TABLE)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def _tokenize(text: str) -> list[str]:
    return normalize_answer(text).split()


# ── Metrics ────────────────────────────────────────────────────────────────────


def exact_match(gold: str, prediction: str) -> bool:
    """Normalized exact match."""
    return normalize_answer(gold) == normalize_answer(prediction)


def token_f1(gold: str, prediction: str) -> float:
    """Token-level F1 between *gold* and *prediction* (Rajpurkar et al. style).

    Returns a float in [0, 1].  Returns 1.0 if both are empty.
    """
    gold_tokens = _tokenize(gold)
    pred_tokens = _tokenize(prediction)
    if not gold_tokens and not pred_tokens:
        return 1.0
    if not gold_tokens or not pred_tokens:
        return 0.0
    gold_counter = Counter(gold_tokens)
    pred_counter = Counter(pred_tokens)
    common = sum((gold_counter & pred_counter).values())
    if common == 0:
        return 0.0
    precision = common / len(pred_tokens)
    recall = common / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


def score_row(row: EvalRow, prediction: str) -> dict[str, Any]:
    """Compute all metrics for a single eval row.

    Returns a dict with keys: ``id``, ``exact_match``, ``token_f1``,
    ``question_type``, ``question_reasoning``, ``ticker``.
    """
    em = exact_match(row.expected_answer, prediction)
    f1 = token_f1(row.expected_answer, prediction)
    return {
        "id": row.id,
        "exact_match": em,
        "token_f1": round(f1, 4),
        "question_type": row.question_type,
        "question_reasoning": row.question_reasoning,
        "ticker": row.company_ticker_symbol,
    }


def aggregate_scores(scored_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate scored rows into overall + per-question-type summary.

    Returns::

        {
            "n": int,
            "exact_match": float,      # fraction
            "token_f1_mean": float,
            "by_question_type": {
                "<type>": {"n": int, "exact_match": float, "token_f1_mean": float},
                ...
            },
        }
    """
    if not scored_rows:
        return {
            "n": 0,
            "exact_match": 0.0,
            "token_f1_mean": 0.0,
            "by_question_type": {},
        }

    n = len(scored_rows)
    overall_em = sum(1 for r in scored_rows if r["exact_match"]) / n
    overall_f1 = sum(r["token_f1"] for r in scored_rows) / n

    by_type: dict[str, list[dict[str, Any]]] = {}
    for r in scored_rows:
        qt = r["question_type"] or "UNKNOWN"
        by_type.setdefault(qt, []).append(r)

    bucket_summary = {}
    for qt, rows in sorted(by_type.items()):
        bn = len(rows)
        bucket_summary[qt] = {
            "n": bn,
            "exact_match": round(sum(1 for r in rows if r["exact_match"]) / bn, 4),
            "token_f1_mean": round(sum(r["token_f1"] for r in rows) / bn, 4),
        }

    return {
        "n": n,
        "exact_match": round(overall_em, 4),
        "token_f1_mean": round(overall_f1, 4),
        "by_question_type": bucket_summary,
    }
