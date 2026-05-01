"""FinanceBench loader + schema smoke tests (Phase 21).

Fully offline — uses the tiny synthetic fixture in tests/fixtures/.
No network, no LLM, no FinanceBench data directory required.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

_FIXTURES = Path(__file__).parent / "fixtures"
_QUESTIONS_FIXTURE = _FIXTURES / "financebench_sample.jsonl"
_DOCUMENTS_FIXTURE = _FIXTURES / "financebench_documents_sample.jsonl"


# ─── schema ───────────────────────────────────────────────────────────────────


def test_financebench_row_from_dict():
    from evals.financebench.schema import FinanceBenchRow

    d = {
        "financebench_id": "TEST_001",
        "question": "What was revenue?",
        "answer": "$5B",
        "evidence": [
            {
                "evidence_text": "Revenue was $5B",
                "evidence_page_num": 10,
                "evidence_source_name": "10K",
                "evidence_source_type": "10-K",
            }
        ],
        "doc_name": "TEST_DOC",
        "question_type": "REVENUE",
        "question_reasoning": "SINGLE_HOP",
        "company_ticker_symbol": "TST",
        "company_name": "Test Co",
    }
    row = FinanceBenchRow.from_dict(d)
    assert row.financebench_id == "TEST_001"
    assert row.question == "What was revenue?"
    assert row.answer == "$5B"
    assert len(row.evidence) == 1
    assert row.evidence[0].evidence_page_num == 10
    assert row.company_ticker_symbol == "TST"


def test_financebench_row_missing_optional_fields():
    from evals.financebench.schema import FinanceBenchRow

    row = FinanceBenchRow.from_dict({"financebench_id": "X", "question": "Q?", "answer": "A"})
    assert row.doc_name == ""
    assert row.evidence == []
    assert row.question_type == ""


def test_evidence_span_from_dict():
    from evals.financebench.schema import EvidenceSpan

    span = EvidenceSpan.from_dict({"evidence_text": "txt", "evidence_page_num": 7})
    assert span.evidence_text == "txt"
    assert span.evidence_page_num == 7


def test_evidence_span_from_empty_dict():
    from evals.financebench.schema import EvidenceSpan

    span = EvidenceSpan.from_dict({})
    assert span.evidence_text == ""
    assert span.evidence_page_num is None


def test_financebench_doc_info_from_dict():
    from evals.financebench.schema import FinanceBenchDocInfo

    doc = FinanceBenchDocInfo.from_dict(
        {
            "doc_name": "ACME_10K",
            "doc_type": "10-K",
            "company_ticker_symbol": "ACME",
            "year_of_report": "2022",
        }
    )
    assert doc.doc_name == "ACME_10K"
    assert doc.doc_type == "10-K"
    assert doc.year_of_report == "2022"


def test_eval_row_from_financebench():
    from evals.financebench.schema import EvalRow, FinanceBenchRow

    row = FinanceBenchRow.from_dict(
        {
            "financebench_id": "ID_001",
            "question": "What is revenue?",
            "answer": "$10B",
            "question_type": "REVENUE",
            "company_ticker_symbol": "AAPL",
            "company_name": "Apple Inc.",
        }
    )
    eval_row = EvalRow.from_financebench(row)
    assert eval_row.id == "ID_001"
    assert eval_row.input == "What is revenue?"
    assert eval_row.expected_answer == "$10B"
    assert eval_row.question_type == "REVENUE"
    assert eval_row.company_ticker_symbol == "AAPL"


# ─── loader ───────────────────────────────────────────────────────────────────


def test_load_questions_from_fixture():
    from evals.financebench.load_dataset import load_questions

    rows = load_questions(_QUESTIONS_FIXTURE)
    assert len(rows) == 2
    assert rows[0].financebench_id == "SYNTHETIC_0001"
    assert rows[0].answer == "$12.5 billion"
    assert rows[0].question_type == "REVENUE"


def test_load_questions_evidence_parsed():
    from evals.financebench.load_dataset import load_questions

    rows = load_questions(_QUESTIONS_FIXTURE)
    assert len(rows[0].evidence) == 1
    assert rows[0].evidence[0].evidence_page_num == 42


def test_load_documents_from_fixture():
    from evals.financebench.load_dataset import load_documents

    docs = load_documents(_DOCUMENTS_FIXTURE)
    assert "ACME_2022_10K" in docs
    assert docs["ACME_2022_10K"].doc_type == "10-K"
    assert docs["ACME_2022_10K"].year_of_report == "2022"


def test_join_dataset_populates_doc_fields():
    from evals.financebench.load_dataset import (
        join_dataset,
        load_documents,
        load_questions,
    )

    rows = load_questions(_QUESTIONS_FIXTURE)
    docs = load_documents(_DOCUMENTS_FIXTURE)
    joined = join_dataset(rows, docs)
    assert joined[0].doc_type == "10-K"
    assert joined[0].year_of_report == "2022"


def test_join_dataset_missing_doc_is_skipped():
    from evals.financebench.load_dataset import join_dataset
    from evals.financebench.schema import FinanceBenchRow

    rows = [
        FinanceBenchRow.from_dict(
            {
                "financebench_id": "X",
                "question": "Q",
                "answer": "A",
                "doc_name": "NO_SUCH_DOC",
            }
        )
    ]
    join_dataset(rows, {})
    assert rows[0].doc_type == ""  # unchanged


def test_to_eval_rows_converts_all():
    from evals.financebench.load_dataset import load_questions, to_eval_rows

    rows = load_questions(_QUESTIONS_FIXTURE)
    eval_rows = to_eval_rows(rows)
    assert len(eval_rows) == 2
    assert eval_rows[0].id == "SYNTHETIC_0001"
    assert eval_rows[1].question_type == "MARGINS"


def test_load_questions_missing_file_raises():
    from evals.financebench.load_dataset import load_questions

    with pytest.raises(FileNotFoundError, match="not found"):
        load_questions(Path("/nonexistent/file.jsonl"))


def test_iter_jsonl_skips_blank_and_bad_lines(tmp_path):
    from evals.financebench.load_dataset import _iter_jsonl

    p = tmp_path / "test.jsonl"
    p.write_text('{"a": 1}\n\n{bad}\n{"b": 2}\n', encoding="utf-8")
    results = list(_iter_jsonl(p))
    assert len(results) == 2
    assert results[0] == {"a": 1}
    assert results[1] == {"b": 2}


def test_data_dir_from_env_absent(monkeypatch):
    from evals.financebench.load_dataset import data_dir_from_env

    monkeypatch.delenv("FINANCEBENCH_DATA_DIR", raising=False)
    assert data_dir_from_env() is None


def test_data_dir_from_env_set(monkeypatch, tmp_path):
    from evals.financebench.load_dataset import data_dir_from_env

    monkeypatch.setenv("FINANCEBENCH_DATA_DIR", str(tmp_path))
    result = data_dir_from_env()
    assert result == tmp_path.resolve()


# ─── metrics ──────────────────────────────────────────────────────────────────


def test_normalize_strips_currency_and_percent():
    from evals.financebench.metrics import normalize_answer

    assert normalize_answer("$12.5 billion") == "125 billion"
    assert normalize_answer("18.4%") == "184"


def test_normalize_removes_thousand_commas():
    from evals.financebench.metrics import normalize_answer

    assert normalize_answer("1,234,567") == "1234567"


def test_normalize_lowercases_and_strips():
    from evals.financebench.metrics import normalize_answer

    assert normalize_answer("  Total Revenue  ") == "total revenue"


def test_exact_match_equal():
    from evals.financebench.metrics import exact_match

    assert exact_match("$12.5 billion", "$12.5 billion") is True
    assert exact_match("$12.5 billion", "12.5 billion") is True  # $ stripped


def test_exact_match_not_equal():
    from evals.financebench.metrics import exact_match

    assert exact_match("$12.5 billion", "$13 billion") is False


def test_token_f1_perfect():
    from evals.financebench.metrics import token_f1

    assert token_f1("hello world", "hello world") == 1.0


def test_token_f1_zero():
    from evals.financebench.metrics import token_f1

    assert token_f1("apple", "banana") == 0.0


def test_token_f1_partial():
    from evals.financebench.metrics import token_f1

    f1 = token_f1("the quick brown fox", "the quick cat")
    assert 0 < f1 < 1


def test_token_f1_empty_both():
    from evals.financebench.metrics import token_f1

    assert token_f1("", "") == 1.0


def test_token_f1_one_empty():
    from evals.financebench.metrics import token_f1

    assert token_f1("answer", "") == 0.0


def test_score_row():
    from evals.financebench.metrics import score_row
    from evals.financebench.schema import EvalRow

    row = EvalRow(
        id="TEST_001",
        input="Q",
        expected_answer="$12.5 billion",
        question_type="REVENUE",
        company_ticker_symbol="ACME",
    )
    result = score_row(row, "$12.5 billion")
    assert result["exact_match"] is True
    assert result["token_f1"] == 1.0
    assert result["id"] == "TEST_001"
    assert result["question_type"] == "REVENUE"


def test_score_row_mismatch():
    from evals.financebench.metrics import score_row
    from evals.financebench.schema import EvalRow

    row = EvalRow(id="X", input="Q", expected_answer="$5 billion")
    result = score_row(row, "$10 billion")
    assert result["exact_match"] is False


def test_aggregate_scores_empty():
    from evals.financebench.metrics import aggregate_scores

    summary = aggregate_scores([])
    assert summary["n"] == 0
    assert summary["exact_match"] == 0.0


def test_aggregate_scores_all_correct():
    from evals.financebench.metrics import aggregate_scores

    rows = [
        {
            "id": "A",
            "exact_match": True,
            "token_f1": 1.0,
            "question_type": "REVENUE",
            "question_reasoning": "SINGLE_HOP",
            "ticker": "X",
        },
        {
            "id": "B",
            "exact_match": True,
            "token_f1": 1.0,
            "question_type": "MARGINS",
            "question_reasoning": "SINGLE_HOP",
            "ticker": "Y",
        },
    ]
    summary = aggregate_scores(rows)
    assert summary["n"] == 2
    assert summary["exact_match"] == 1.0
    assert "REVENUE" in summary["by_question_type"]
    assert "MARGINS" in summary["by_question_type"]


def test_aggregate_scores_partial():
    from evals.financebench.metrics import aggregate_scores

    rows = [
        {
            "id": "A",
            "exact_match": True,
            "token_f1": 1.0,
            "question_type": "REVENUE",
            "question_reasoning": "S",
            "ticker": "X",
        },
        {
            "id": "B",
            "exact_match": False,
            "token_f1": 0.5,
            "question_type": "REVENUE",
            "question_reasoning": "S",
            "ticker": "Y",
        },
    ]
    summary = aggregate_scores(rows)
    assert summary["exact_match"] == 0.5
    assert summary["by_question_type"]["REVENUE"]["exact_match"] == 0.5
