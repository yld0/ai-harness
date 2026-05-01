"""FinanceBench JSONL loader (Phase 21).

Pure Python (no pandas/polars).  Two entry points:

- :func:`load_questions` — parse ``financebench_open_source.jsonl``
- :func:`load_documents` — parse ``financebench_document_information.jsonl``
- :func:`join_dataset` — optionally augment questions with document metadata
- :func:`to_eval_rows` — convert to internal :class:`~.schema.EvalRow` format

Follows the "skip if vendor dir missing" pattern: callers can call
:func:`data_dir_from_env` and skip the test if it returns ``None``.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Iterator

from evals.financebench.schema import (
    EvalRow,
    FinanceBenchDocInfo,
    FinanceBenchRow,
)

logger = logging.getLogger(__name__)

# Upstream JSONL file names.
QUESTIONS_FILE = "financebench_open_source.jsonl"
DOCUMENTS_FILE = "financebench_document_information.jsonl"


def data_dir_from_env() -> Path | None:
    """Return the data directory from ``FINANCEBENCH_DATA_DIR`` env, or ``None``.

    Use this to skip tests when the optional dataset is not available::

        data_dir = data_dir_from_env()
        if data_dir is None:
            pytest.skip("FINANCEBENCH_DATA_DIR not set")
    """
    raw = os.environ.get("FINANCEBENCH_DATA_DIR", "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser().resolve()
    if not p.is_dir():
        logger.warning("FINANCEBENCH_DATA_DIR=%s does not exist", p)
        return None
    return p


def _iter_jsonl(path: Path) -> Iterator[dict]:
    """Yield parsed objects from a JSONL file; skip blank lines and parse errors."""
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning(
                    "%s line %d: JSON parse error (%s); skipping",
                    path.name,
                    lineno,
                    exc,
                )


def load_questions(path: Path) -> list[FinanceBenchRow]:
    """Load all rows from a FinanceBench questions JSONL file."""
    if not path.is_file():
        raise FileNotFoundError(f"FinanceBench questions file not found: {path}")
    rows = [FinanceBenchRow.from_dict(d) for d in _iter_jsonl(path)]
    logger.info("Loaded %d FinanceBench questions from %s", len(rows), path)
    return rows


def load_documents(path: Path) -> dict[str, FinanceBenchDocInfo]:
    """Load document info from JSONL and return a ``{doc_name: FinanceBenchDocInfo}`` index."""
    if not path.is_file():
        raise FileNotFoundError(f"FinanceBench documents file not found: {path}")
    docs: dict[str, FinanceBenchDocInfo] = {}
    for d in _iter_jsonl(path):
        doc = FinanceBenchDocInfo.from_dict(d)
        if doc.doc_name:
            docs[doc.doc_name] = doc
    logger.info("Loaded %d FinanceBench document records from %s", len(docs), path)
    return docs


def join_dataset(
    questions: list[FinanceBenchRow],
    documents: dict[str, FinanceBenchDocInfo],
) -> list[FinanceBenchRow]:
    """Augment each question row with document-level metadata (mutates in place).

    Fields populated: ``doc_type``, ``period_of_report``, ``year_of_report``.
    Missing document entries are silently skipped.
    """
    for row in questions:
        doc_info = documents.get(row.doc_name)
        if doc_info:
            row.doc_type = doc_info.doc_type
            row.period_of_report = doc_info.period_of_report
            row.year_of_report = doc_info.year_of_report
    return questions


def to_eval_rows(rows: list[FinanceBenchRow]) -> list[EvalRow]:
    """Convert upstream rows to harness :class:`~.schema.EvalRow` format."""
    return [EvalRow.from_financebench(r) for r in rows]


def load_eval_dataset(
    data_dir: Path,
    *,
    join_docs: bool = True,
    max_rows: int | None = None,
) -> list[EvalRow]:
    """Convenience: load, optionally join, and convert to eval rows.

    Parameters
    ----------
    data_dir:
        Directory containing the FinanceBench JSONL files.
    join_docs:
        If True (default), attempt to join with ``financebench_document_information.jsonl``.
    max_rows:
        Limit to the first N rows after loading (useful for quick local runs).
    """
    questions = load_questions(data_dir / QUESTIONS_FILE)
    if join_docs:
        docs_path = data_dir / DOCUMENTS_FILE
        if docs_path.is_file():
            docs = load_documents(docs_path)
            join_dataset(questions, docs)
        else:
            logger.warning("Document info file not found (%s); skipping join", docs_path)
    if max_rows is not None:
        questions = questions[:max_rows]
    return to_eval_rows(questions)
