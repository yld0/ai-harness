"""FinanceBench row schemas (Phase 21).

Two levels:
- :class:`FinanceBenchRow` — upstream field names from the JSONL files.
- :class:`EvalRow` — internal harness eval format (parallel to ``financial_qa_golden.yaml``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvidenceSpan:
    """A single evidence item from the upstream FinanceBench annotation."""

    evidence_text: str = ""
    evidence_page_num: int | None = None
    evidence_source_name: str = ""
    evidence_source_type: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EvidenceSpan":
        return cls(
            evidence_text=str(d.get("evidence_text") or ""),
            evidence_page_num=d.get("evidence_page_num"),
            evidence_source_name=str(d.get("evidence_source_name") or ""),
            evidence_source_type=str(d.get("evidence_source_type") or ""),
        )


@dataclass
class FinanceBenchRow:
    """Upstream FinanceBench question row (from ``financebench_open_source.jsonl``)."""

    financebench_id: str
    question: str
    answer: str
    evidence: list[EvidenceSpan] = field(default_factory=list)
    doc_name: str = ""
    question_type: str = ""
    question_reasoning: str = ""
    domain: str = ""
    company_name: str = ""
    company_ticker_symbol: str = ""
    # document info fields (populated after join)
    doc_type: str = ""
    period_of_report: str = ""
    year_of_report: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FinanceBenchRow":
        evidence_raw = d.get("evidence") or []
        if not isinstance(evidence_raw, list):
            evidence_raw = []
        return cls(
            financebench_id=str(d.get("financebench_id") or ""),
            question=str(d.get("question") or ""),
            answer=str(d.get("answer") or ""),
            evidence=[EvidenceSpan.from_dict(e) if isinstance(e, dict) else EvidenceSpan() for e in evidence_raw],
            doc_name=str(d.get("doc_name") or ""),
            question_type=str(d.get("question_type") or ""),
            question_reasoning=str(d.get("question_reasoning") or ""),
            domain=str(d.get("domain") or ""),
            company_name=str(d.get("company_name") or ""),
            company_ticker_symbol=str(d.get("company_ticker_symbol") or ""),
        )


@dataclass
class FinanceBenchDocInfo:
    """Upstream document information row (from ``financebench_document_information.jsonl``)."""

    doc_name: str
    doc_type: str = ""
    company_name: str = ""
    company_ticker_symbol: str = ""
    period_of_report: str = ""
    year_of_report: str = ""
    fiscal_year_end: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FinanceBenchDocInfo":
        return cls(
            doc_name=str(d.get("doc_name") or ""),
            doc_type=str(d.get("doc_type") or ""),
            company_name=str(d.get("company_name") or ""),
            company_ticker_symbol=str(d.get("company_ticker_symbol") or ""),
            period_of_report=str(d.get("period_of_report") or ""),
            year_of_report=str(d.get("year_of_report") or ""),
            fiscal_year_end=str(d.get("fiscal_year_end") or ""),
        )


@dataclass
class EvalRow:
    """Internal harness eval record (parallel to financial_qa_golden.yaml format).

    Deliberately separate from :class:`FinanceBenchRow` so harness-specific
    fields (tier, route, tool expectations) can be added manually without
    polluting the upstream schema.
    """

    id: str
    input: str  # question text
    expected_answer: str  # gold answer string
    evidence_spans: list[EvidenceSpan] = field(default_factory=list)
    doc_name: str = ""
    question_type: str = ""
    question_reasoning: str = ""
    company_ticker_symbol: str = ""
    company_name: str = ""

    @classmethod
    def from_financebench(cls, row: FinanceBenchRow) -> "EvalRow":
        return cls(
            id=row.financebench_id,
            input=row.question,
            expected_answer=row.answer,
            evidence_spans=row.evidence,
            doc_name=row.doc_name,
            question_type=row.question_type,
            question_reasoning=row.question_reasoning,
            company_ticker_symbol=row.company_ticker_symbol,
            company_name=row.company_name,
        )
