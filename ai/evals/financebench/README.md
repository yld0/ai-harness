# FinanceBench Optional Eval Track (Phase 21)

An **optional, slow** evaluation track using the open
[FinanceBench](https://github.com/patronus-ai/financebench) dataset — 150
annotated financial Q&A rows with gold answers, evidence spans, and linked
SEC filing PDFs.

This **does not replace** `evals/financial_qa_golden.yaml` (Phase 8 primary
contract).  It complements Phase 8 for document-grounded financial QA
benchmarking and comparability with published work.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Phase 8 scaffold | `pytest`, `deepeval`, slow/live markers |
| `FINANCEBENCH_DATA_DIR` | Path to a local FinanceBench data directory |
| `RUN_FINANCEBENCH=1` | Explicit opt-in env flag |
| LLM / API keys (Mode B) | For agent-based answering (optional; stub baseline always runs) |

---

## Data Acquisition

The FinanceBench open-source sample is not vendored in this repo due to size
and licensing.  Use the **download script** approach (Option 2 from the plan):

```bash
# Clone FinanceBench to a gitignored local path
git clone https://github.com/patronus-ai/financebench /tmp/financebench

# Set the data directory
export FINANCEBENCH_DATA_DIR=/tmp/financebench/data
```

The `data/` directory should contain:
- `financebench_open_source.jsonl` — 150 open Q&A rows (questions file)
- `financebench_document_information.jsonl` — document metadata (optional join)
- `pdfs/` — SEC filing PDFs (large; not required for Mode B)

> **Do not commit** `FINANCEBENCH_DATA_DIR` contents or PDFs to this repository.
> The `.gitignore` excludes `evals/financebench/vendor/`.

---

## Answering Mode

This implementation uses **Mode B: tool/API-only agent without PDFs**.

| Mode | Description |
|------|-------------|
| A | RAG over bundled SEC PDFs (matches benchmark pipeline) |
| **B (implemented)** | Agent calls harness tools (FMP, web search) without reading PDFs |
| C | Hybrid RAG + tools |

**Caveat:** Mode B scores are expected to be **lower** than the paper's
reported numbers, which use a retrieval pipeline over the actual filings.
Do not compare Mode B results directly to the paper's Table 1 without
documenting this caveat in any published report.

---

## Running the Eval

### Default CI (no FinanceBench)
```bash
cd ai
uv run pytest -m "not slow and not live"   # FinanceBench tests skipped
```

### Offline smoke tests only (uses synthetic fixture)
```bash
uv run pytest tests/test_financebench_loader_smoke.py -q
```

### Full FinanceBench (slow, opt-in)
```bash
export RUN_FINANCEBENCH=1
export FINANCEBENCH_DATA_DIR=/tmp/financebench/data
cd ai && uv run pytest tests/test_financebench_eval_optional.py -m slow -s
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FINANCEBENCH_DATA_DIR` | — | Path to directory with JSONL files |
| `RUN_FINANCEBENCH` | — | Set to `1` to enable full eval tests |

---

## Metrics

| Metric | Description |
|--------|-------------|
| **Exact Match** (primary) | Normalized: strip `$`, `%`, thousand commas, lowercase, strip punctuation |
| **Token F1** | Precision×recall F1 over whitespace tokens (Rajpurkar et al.) |

Per-`question_type` breakdown is included in `aggregate_scores()` output.
Map to Langfuse spans via `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` (optional).

---

## Dataset Structure

Internal eval record (after `to_eval_rows()`):

| Field | Source | Notes |
|-------|--------|-------|
| `id` | `financebench_id` | Unique row identifier |
| `input` | `question` | The financial question |
| `expected_answer` | `answer` | Gold answer string |
| `evidence_spans` | `evidence` | List of source text + page annotations |
| `doc_name` | `doc_name` | Filing document identifier |
| `question_type` | `question_type` | e.g. `REVENUE`, `MARGINS`, `RATIOS` |
| `question_reasoning` | `question_reasoning` | `SINGLE_HOP` / `MULTI_HOP` |
| `company_ticker_symbol` | `company_ticker_symbol` | e.g. `AAPL` |

---

## Limitations vs the Paper

- Mode B has no access to actual PDF content; tools use live or cached APIs.
- The open-source sample (150 Q) is a subset of the full dataset (10,231 Q).
- Scores are not directly comparable to [Nair et al. 2023](https://arxiv.org/abs/2311.11944) without a matching retrieval pipeline.

---

## Citation

If you use FinanceBench data in publications, cite the upstream work:

```bibtex
@misc{islam2023financebench,
      title={FinanceBench: A New Benchmark for Financial Question Answering},
      author={Pranab Islam and Anand Kannappan and Douwe Kiela and Rebecca Qian
              and Nino Scherrer and Bertie Vidgen},
      year={2023},
      eprint={2311.11944},
      archivePrefix={arXiv},
      primaryClass={cs.CL}
}
```

Source: <https://github.com/patronus-ai/financebench>

---

## Related

- [Phase 8: Tests & Evals](../../plans/09-phase-8-tests-evals.md) — primary golden YAML eval policy
- [Phase 22: Eval tiers](../../plans/23-phase-22-eval-tiers.md) — T0–T3 classification
- [evals/financial_qa_golden.yaml](../financial_qa_golden.yaml) — harness-owned contract cases
