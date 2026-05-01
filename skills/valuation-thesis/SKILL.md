---
name: valuation-thesis
description: End-to-end pipeline for producing financial valuation write-ups and investment theses — from data gathering through model building, narrative drafting, and review. Covers equities, private companies, and macro theses.
version: 1.0.0
metadata:
  tags: [finance, valuation, investment-thesis, research, dcf, comparables]
  category: finance
  related_skills: [arxiv, polymarket, para-memory-files, plan]
---

# Valuation Thesis Pipeline

End-to-end pipeline for producing investment theses and valuation write-ups for equities,
private companies, or macro positions.

This is **not a linear pipeline** — it is iterative. New data triggers model updates.
New information triggers thesis revision.

```
Phase 0: Setup & Context
    │
    ▼
Phase 1: Data Gathering ──► Phase 2: Model Building
    │                              │
    ▼                              ▼
Phase 3: Thesis Drafting ◄── Phase 4: Sensitivity / Scenario
    │
    ▼
Phase 5: Self-Review & Revision ──► Final Output
```

---

## When to Use This Skill

Use when:
- User asks to value a company, asset, or position
- User asks to write an investment thesis or research note
- User wants a DCF, comps, or sum-of-parts analysis
- User wants a bull/base/bear scenario breakdown
- User asks to synthesize financial data into a narrative

---

## Core Philosophy

1. **Data first, narrative second.** Never write a thesis before collecting the underlying data.
2. **Cite all figures.** Every number must trace to a source (10-K, earnings call, FMP API, etc.).
3. **Scenarios are not optional.** Every valuation must include at minimum a base case and a bear case.
4. **State the key assumption.** One variable drives most of the value — identify it and test it.
5. **Separate facts from judgements.** Facts come from data; judgements must be labeled as such.

---

## Phase 0: Setup & Context

1. Identify the target: ticker, company name, or macro theme.
2. Confirm what type of output is needed: thesis note, DCF model, comp table, scenario analysis, or all.
3. Read existing memory files for the ticker/space under `$MEMORY_ROOT/users/<user_id>/tickers/<ticker>/`.
4. Check what data sources are available: FMP API key, web search, SEC EDGAR.

---

## Phase 1: Data Gathering

### Financial Statements

Use the `fmp` tool or `web_fetch` to pull:
- Income statement (5Y trailing annual + trailing 12 months)
- Balance sheet (latest quarter)
- Cash flow statement (5Y trailing annual)
- Segment revenue breakdown if available

### Market Data

- Current price, market cap, enterprise value
- 52-week range, beta
- Consensus estimates (EPS, revenue) for next 2 fiscal years

### Qualitative Context

- Latest earnings call transcript (key quotes on growth drivers, margins, guidance)
- Recent news (M&A, regulatory, macro)
- Competitor landscape

---

## Phase 2: Model Building

### DCF (Discounted Cash Flow)

```
Revenue growth assumptions (Y1–Y5, terminal)
EBIT margin assumptions
D&A, capex, working capital changes
→ Free cash flow projection
WACC = risk-free rate + beta × equity risk premium + debt cost × (1-tax) × leverage
Terminal value = FCF_terminal / (WACC - terminal_growth)
Equity value = PV(FCFs) + PV(terminal) - net debt
Implied price = equity value / diluted shares
```

### Comps (Comparable Companies)

Build a table:

| Company | EV/EBITDA | EV/Sales | P/E | NTM Rev Growth | NTM EBIT Margin |
|---------|-----------|----------|-----|----------------|-----------------|

Apply median or selected-peer multiples to the subject company.

### Scenario Analysis

| Scenario | Key Assumption | Implied Price | Upside/Downside |
|----------|---------------|---------------|-----------------|
| Bull     | …             | …             | …               |
| Base     | …             | …             | …               |
| Bear     | …             | …             | …               |

---

## Phase 3: Thesis Drafting

### Structure

```markdown
# [Company] Investment Thesis — [Date]

## Summary
One-paragraph view: Buy / Hold / Sell, target price, time horizon, and the one-sentence core thesis.

## Business Overview
What the company does, key segments, competitive position.

## Investment Catalysts
Numbered list of 3–5 near-term catalysts.

## Valuation
Present the model output: DCF implied price, comps range, and scenario table.
State the key assumption and the sensitivity to it.

## Risks
Bull case risks and bear case risks. Be specific — no generic "macro uncertainty".

## Conclusion
Restate the view with conviction language.
```

### Writing Rules

- Every number has a source in parentheses: `(10-K FY2024)`, `(Bloomberg consensus)`, `(FMP API)`.
- Use present tense for facts, future tense for projections.
- Flag all judgement calls explicitly: "We assume 15% margin expansion by FY2026 — this is the key upside driver."
- Keep the summary under 150 words.

---

## Phase 4: Sensitivity / Scenario Deep Dive

When asked to stress-test the model:

1. Identify the 2–3 variables with the highest impact on implied price (usually: revenue growth, margin, WACC / exit multiple).
2. Build a sensitivity table for each pair (e.g., growth × margin → implied price grid).
3. Define probability weights for scenarios if asked.
4. State the break-even assumption: "The stock is fairly valued if FY2026 revenue reaches $X."

---

## Phase 5: Self-Review

Before delivering, check:

- [ ] Every number has a source
- [ ] DCF assumptions are stated explicitly
- [ ] At least base + bear scenario present
- [ ] Key assumption identified and sensitivity shown
- [ ] Risks section is specific (not generic)
- [ ] Summary is ≤150 words and states the view clearly

---

## Output Formats

- **Thesis note**: full markdown document (save to `$MEMORY_ROOT/users/<user_id>/tickers/<ticker>/thesis.md`)
- **Model summary**: structured YAML (save to `valuation.yaml` alongside)
- **Comp table**: inline markdown table
- **Scenario table**: inline markdown table

---

## Tools

| Task | Tool |
|------|------|
| Financial statements | `fmp` tool or `web_fetch` |
| News, context | `web_search` / `web_fetch` |
| SEC filings | `web_fetch` → EDGAR |
| Existing memory | `memory_search` |
| Save output | `write_file` to PARA ticker path |
