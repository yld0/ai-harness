# Memory System Design — Financial AI Harness

Extends the PARA memory files skill (`references-skills/para-memory-files/`) with financial-domain awareness, temporal validity, and multi-user scoping.

Reference implementations:
- Paperclip PARA: `references-skills/para-memory-files/SKILL.md`
- OpenClaw temporal decay: `references/openclaw-main/extensions/memory-core/src/memory/temporal-decay.ts`
- Dexter: `https://github.com/virattt/dexter/blob/main/src/memory/temporal-decay.ts`

---

## 0. How Memory Files Are Updated

There is no server-side memory engine. The agent itself reads and writes plain files using standard filesystem tools. The skill (`SKILL.md`) is loaded into the agent's context and teaches it *what* to write, *where*, and *when*. When the agent decides something is worth remembering, it calls file-write tools directly:

```
Agent → filesystem write tool → $MEMORY_ROOT/users/<user_id>/life/tickers/MSFT/items.yaml
```

### Three update triggers

#### 1. During conversation (real-time)

| File | Timing | What gets written |
|---|---|---|
| `items.yaml` | Immediately when a durable fact surfaces | Atomic YAML fact appended to the entity's file |
| `memory/YYYY-MM-DD.md` | Continuously during conversation | Timeline entries — what was discussed, decided, asked |
| `MEMORY.md` | Whenever a new user pattern is learned | Tacit knowledge — preferences, habits, communication style |

If a user says "I think MSFT is overvalued at 35x P/E," the agent should write that fact to `tickers/MSFT/items.yaml` right then and log the event to today's daily note.

#### 2. During heartbeats (scheduled extraction)

A heartbeat is a server-scheduled agent run — triggered by a timer, an issue assignment, a comment mention, or an approval flow. The server wakes the agent and it runs through a checklist. Step 7 of that checklist is fact extraction:

1. Check for new conversations since last extraction.
2. Extract durable facts to the relevant entity in `life/` (PARA).
3. Update `memory/YYYY-MM-DD.md` with timeline entries.
4. Update access metadata (`last_accessed`, `access_count`) for any referenced facts.

This is the catch-up pass — anything the agent missed during live conversation gets extracted here. It also handles access tracking: if the user mentioned MSFT three times in a conversation, the heartbeat bumps the access count on MSFT-related facts.

#### 3. Weekly synthesis (batch rewrite)

The agent reads all facts in `items.yaml` for each entity, applies decay rules (Current/Fading/Historical groupings from section 5), and rewrites `summary.md`. Cold facts drop out of the summary but remain in `items.yaml`. In the financial domain, `thesis.md`, `valuation.yaml`, and `consensus.yaml` are also rebuilt/refreshed during this pass. For spaces, the agent regenerates `summary.md` and the default report style. For the user root, rewrite `goals/summary.md` from `goals/items.yaml` when any goal changed during the week.

### Summary

| Trigger | What gets written | When |
|---|---|---|
| User says something factual | `items.yaml` (fact), `memory/YYYY-MM-DD.md` (timeline) | Immediately during conversation |
| Heartbeat fires | Missed facts → `items.yaml`, daily notes, access metadata | Server-scheduled (timer, event, mention) |
| Weekly synthesis | `summary.md` rewritten with decay, `thesis.md` rebuilt, `valuation.yaml`/`consensus.yaml` refreshed, `goals/summary.md` from goals `items.yaml`, space reports generated | Weekly (or on demand) |
| User pattern learned | `MEMORY.md` updated | Whenever noticed |
| User states portfolio target / progress | `goals/items.yaml` + `goals/summary.md` | Immediately or on heartbeat |

### What the harness must provide

1. **Include the skill in the agent's context** so it knows the rules.
2. **Provide filesystem write tools** so the agent can create/edit files.
3. **Schedule heartbeats** (or equivalent cron/event triggers) so extraction and synthesis happen between user conversations.
4. **Scope `$MEMORY_ROOT`** per user — resolved from session context.
5. **Provide `qmd`** (or equivalent semantic search) so the agent can recall facts without grepping.

---

## 1. The Problem

Financial facts have fundamentally different lifespans. The base PARA schema treats all facts identically — access-count decay with Hot/Warm/Cold tiers. OpenClaw uses a single exponential half-life. Neither is right for finance:

- **"MSFT guided $64B revenue for Q3 FY2026"** — has a known expiry (the quarter ends).
- **"MSFT is overvalued at 35x P/E"** — decays continuously as price and earnings change.
- **"Satya Nadella became CEO in 2014"** — never decays.

A decayed fact shouldn't disappear. "MSFT was overvalued last June" is still useful for thesis tracking and pattern analysis. Decay affects retrieval priority, not existence.

---

## 2. Validity Types

Every fact declares how it ages via a `validity` field:

| `validity` | Meaning | Decay behavior |
|---|---|---|
| `evergreen` | Permanent. Founding dates, CEO changes, structural facts. | No decay. Always available. |
| `expires` | Has a known end date. Guidance, catalyst dates, quarterly data, earnings estimates. | Hot until `expires` date, then auto-transitions to `status: historical`. |
| `point_in_time` | Observation/opinion at a moment. Valuation calls, sentiment reads, price snapshots. | Continuous exponential decay via half-life. |

### Auto-expiry transition (`expires`)

When `today > expires`:
1. `status` flips from `active` → `historical`
2. Fact text in `summary.md` is rewritten to past tense
3. Fact remains in `items.yaml` with original text plus `transitioned_at` timestamp
4. No decay score — historical facts are filed separately, not penalized

This preserves the record for YoY earnings analysis, thesis review, etc.

---

## 3. Half-Life Decay for `point_in_time` Facts

Exponential decay applied at retrieval time (from OpenClaw):

```
decay_score = base_score × e^(-λ × age_in_days)
λ = ln(2) / half_life_days
```

Half-life varies by financial category:

| Category | `half_life_days` | Rationale |
|---|---|---|
| `price_snapshot` | 3 | Prices change daily. |
| `valuation` | 7 | "Overvalued at 35x P/E" — meaningless if price moves 10%. |
| `sentiment` | 14 | "Market is risk-off" — sentiment shifts over weeks. |
| `analyst_rating` | 30 | Analyst updates are roughly quarterly. |
| `thesis` | 90 | A bull/bear thesis should persist for a quarter unless explicitly revised. |
| `macro` | 30 | Fed policy, inflation reads — monthly cycle. |

Default `half_life_days` when not specified: `14`.

### Access reheat (from Paperclip)

Frequently referenced facts resist decay:

```
effective_half_life = base_half_life × (1 + log₂(1 + access_count))
```

- 0 accesses → base rate (e.g., 7 days for valuation)
- 3 accesses → 2× half-life (14 days)
- 7 accesses → 4× half-life (28 days)

This means "MSFT is overvalued" decays in a week if nobody mentions it, but stays warm for a month if the user keeps discussing MSFT valuation.

---

## 4. Fact Schema (Extended)

Extends the base schema from `references-skills/para-memory-files/references/schemas.md`.

```yaml
- id: MSFT-048
  fact: "MSFT appears overvalued at 35x P/E vs 5yr avg 28x"
  category: valuation           # valuation | price_snapshot | sentiment | analyst_rating | thesis | macro | earnings | guidance | catalyst | structural
  validity: point_in_time       # evergreen | expires | point_in_time
  half_life_days: 7             # only for point_in_time; defaults by category if omitted
  expires: null                 # ISO date, only for validity=expires
  confidence: medium            # low | medium | high
  direction: bearish            # bullish | bearish | neutral (nullable)
  source_type: agent_analysis   # agent_analysis | user_input | api_data | earnings_call | analyst_report | news
  source_ref: "User conversation, 2026-04-10"
  recorded_at: "2026-04-10"    # when the fact was captured
  timestamp: "2026-04-10"      # same as recorded_at (base schema compat)
  status: active                # active | historical | superseded
  superseded_by: null
  transitioned_at: null         # set when status changes to historical
  related_entities:
    - tickers/MSFT
  last_accessed: "2026-04-12"
  access_count: 2
```

### Fields added vs base schema

| Field | Type | Purpose |
|---|---|---|
| `validity` | enum | Declares how the fact ages. |
| `half_life_days` | int (nullable) | Custom half-life for `point_in_time` facts. Falls back to category default. |
| `expires` | ISO date (nullable) | Hard expiry for `expires` validity. |
| `confidence` | enum | How confident the source is in this fact. |
| `direction` | enum (nullable) | Bullish/bearish/neutral signal. |
| `source_type` | enum | Origin of the fact. |
| `source_ref` | string | Specific source (conversation date, filing, article). |
| `recorded_at` | ISO date | When the fact was captured (distinct from `timestamp` for back-dated entries). |
| `transitioned_at` | ISO date (nullable) | When `status` changed to `historical`. |

### Status values expanded

| Status | Meaning |
|---|---|
| `active` | Current, subject to decay rules. |
| `historical` | Auto-transitioned from `expires` or manually archived. Not decayed — just filed separately. |
| `superseded` | Replaced by another fact (`superseded_by` points to the replacement). |

---

## 5. Summary.md Synthesis

When rewriting `summary.md` for an entity, group by temporal status:

```markdown
# MSFT — Summary
Updated: 2026-04-15

## Current
- Management guided $64B revenue Q3 FY2026 [expires: 2026-07-30]
- Azure growth accelerating to 32% YoY [confidence: high]
- Copilot revenue run-rate >$10B [source: earnings call]

## Fading
- Appeared overvalued at 35x P/E vs 5yr avg 28x [recorded: 2026-04-10, decay: 0.47]
- Sell-side consensus is "overweight" [recorded: 2026-03-28, decay: 0.31]

## Historical
- Guided $61B for Q2 FY2026 → actual $62.3B (beat) [expired: 2026-04-30]
- Was trading at 30x P/E in Jan 2026 [recorded: 2026-01-15]
```

### Synthesis rules

1. **Current** — `status: active` AND (`validity: evergreen` OR `validity: expires` with `expires > today` OR `validity: point_in_time` with `decay_score ≥ 0.5`)
2. **Fading** — `status: active` AND `validity: point_in_time` AND `decay_score < 0.5` AND `decay_score ≥ 0.1`
3. **Historical** — `status: historical` OR `decay_score < 0.1`
4. Omit from summary entirely when `decay_score < 0.05` — still in `items.yaml`, retrievable on demand.
5. High `access_count` resists demotion (via reheat formula above).

---

## 6. Folder Structure (Financial Domain)

Replaces generic PARA categories with financial-domain entities:

```text
$MEMORY_ROOT/users/<user_id>/
  USER.md                      # hot: preferences, tone, work habits, profile (~1375 chars target)
  MEMORY.md                    # hot: conventions, tool quirks, durable user-level facts (~2200 chars cap)
  goals/
    summary.md                 # active goals overview (warm — load when discussing portfolio / progress)
    items.yaml                 # structured goal records (see "Goals schema" below)
  life/
    tickers/<SYMBOL>/
      summary.md               # quick context with Current/Fading/Historical
      items.yaml               # atomic facts
      thesis.md                # per-ticker thesis (NOT a user-level thesis/ folder)
      valuation.yaml           # structured valuation data (models, risk/reward, intrinsic value)
      consensus.yaml           # analyst ratings, price targets, market sentiment
    sectors/<name>/
      summary.md
      items.yaml
    spaces/<space_id>/
      summary.md               # latest synthesis of the research space
      items.yaml               # atomic facts extracted from space research
      knowledge-base.md        # synced from Space.knowledgeBase (API)
      sources.yaml             # manifest: files, URLs, YouTube channels
      reports/                 # generated outputs by style, timestamped
        YYYY-MM-DD-report.md
        YYYY-MM-DD-deep-report.md
        YYYY-MM-DD-key-takeaways.md
        YYYY-MM-DD-blog-post.md
        YYYY-MM-DD-tldr.md
        YYYY-MM-DD-summary.md
    watchlists/<id>/
      summary.md
      items.yaml
    people/<name>/             # executives, analysts
      summary.md
      items.yaml
    macros/<topic>/            # fed-policy, inflation, rates
      summary.md
      items.yaml
  memory/
    YYYY-MM-DD.md              # daily notes (research timeline)

$MEMORY_ROOT/global/
  tickers/<SYMBOL>/            # shared cross-user facts (earnings dates, splits, structural)
    summary.md
    items.yaml
  sectors/<name>/
    summary.md
    items.yaml
```

### Multi-user scoping

- Each user gets an isolated `$MEMORY_ROOT/users/<user_id>/` tree.
- `$MEMORY_ROOT/global/` holds shared, user-agnostic facts (earnings dates, splits, structural data).
- Agent resolves `user_id` from session context. All reads/writes are scoped to the active user unless querying global.
- Global facts are `validity: evergreen` or `validity: expires` only — no opinions in global.

### Hot / warm / cold (session context)

Aligns with harness design: not everything loads into the model every turn.

| Tier | Paths | When loaded |
|---|---|---|
| **Hot** | `USER.md`, `MEMORY.md` | Every session start (or every turn if caps stay small) |
| **Warm** | `goals/summary.md`, entity `summary.md` under `life/` | When user discusses portfolio, goals, or a named ticker/space/sector |
| **Cold** | `items.yaml`, `valuation.yaml`, `consensus.yaml`, `memory/YYYY-MM-DD.md`, space `reports/`, skills | On demand via search (`qmd`), tool read, or explicit user request |

Keep `USER.md` and `MEMORY.md` under their character budgets so they can stay in the system prompt snapshot. Push detailed facts into `life/` and daily notes.

### User root vs `life/` — why no `thesis/` folder at top level

Stock theses are **per symbol**. A top-level `user/<id>/thesis/` duplicates the entity model and splits MSFT across two trees. Use **`life/tickers/<SYMBOL>/thesis.md`** only. User-level narrative belongs in `goals/` (portfolio targets) or `USER.md` (investing style), not a separate thesis directory.

### `goals/` — cross-cutting portfolio and life goals

Goals span multiple tickers and spaces (e.g. "reach $500K by 2028", "max 20% in single names"). They live at the user root, not under `life/tickers/`.

**Files:**

- `goals/summary.md` — short markdown the agent can pull when answering "how am I tracking?" or sizing a new position.
- `goals/items.yaml` — list of structured goal records.

**Goal record schema** (`items.yaml` entries; extends the atomic fact pattern with goal-specific fields):

```yaml
- id: goal-001
  title: "Build equity portfolio to $500K"
  description: "Long-term wealth; quality growth at reasonable valuations"
  goal_type: portfolio_value      # portfolio_value | return_target | income | risk_budget | learning | other
  target_value: 500000
  target_currency: USD
  target_date: "2028-12-31"
  validity: expires               # goals usually expire at target_date or when achieved
  status: active                  # active | achieved | paused | abandoned | historical
  progress_note: "~$280K across 12 positions as of 2026-04"
  progress_percent: 56            # optional 0-100 if quantifiable
  strategy: "Concentrate in 15-25 names; trim losers; add on dips"
  constraints:
    - "Max 20% single name"
    - "No leveraged ETFs"
  related_entities:
    - tickers/MSFT
    - tickers/GOOGL
    - watchlists/core-growth
  recorded_at: "2026-01-15"
  last_reviewed: "2026-04-01"
  last_accessed: "2026-04-10"
  access_count: 3
```

**Synthesis:** On weekly pass (or when goals change), rewrite `goals/summary.md` from `active` goals in `items.yaml`. Move `achieved` / `abandoned` goals to `historical` with `transitioned_at` if you want a paper trail (or archive rows in the same file with `status: historical`).

**When the agent updates goals:** User states a new target, progress check-in, or constraint → update `items.yaml` and bump `summary.md`. Heartbeat can reconcile goals mentioned in chat with stale `progress_note` fields.

### `thesis.md` — per-ticker investment thesis

A synthesized markdown document (not YAML) that aggregates the user's investment view:

```markdown
# MSFT Investment Thesis
Updated: 2026-04-15 | Direction: Bullish | Confidence: Medium

## Bull Case
- Azure growth re-accelerating (32% YoY)
- Copilot monetization exceeding expectations ($10B+ run rate)

## Bear Case
- Premium valuation (35x P/E vs 28x 5yr avg)
- Macro headwinds if rates stay elevated

## Risks
- Antitrust regulatory overhang in EU
- Dependency on enterprise IT spending cycle
- AI capex spend may not yield proportional returns

## Growth Opportunities
- Copilot platform effect across Office 365 base (400M+ users)
- Azure AI services (model hosting, fine-tuning)
- Gaming segment stabilizing post-Activision integration

## Key Catalysts
- Q3 FY2026 earnings (2026-07-29) [expires: 2026-07-30]
- Copilot enterprise pricing update expected Q3

## Position
User is long via MSFT shares, added Jan 2026.
```

Rebuilt from `items.yaml` facts during weekly synthesis or on demand. Maps to `StockInvestmentDecision.companyOutlook` (risks, growthOpportunities, uncertainties, competitiveEdge) and `InvestmentOpportunity` from the GraphQL API.

### `valuation.yaml` — structured valuation data

Dedicated file for quantitative valuation data. Separates structured numbers from the opinion-based `thesis.md` and atomic facts in `items.yaml`.

```yaml
symbol: MSFT
updated: "2026-04-15"
validity: point_in_time
half_life_days: 7

intrinsic_value:
  base: 380.00
  low: 340.00
  high: 430.00
  margin_of_safety: 20

models:
  - slug: dcf
    name: "Discounted Cash Flow"
    low: 350.00
    mid: 395.00
    high: 440.00
    suitability: 0.85
    suitability_reason: "Strong free cash flow generation, predictable revenue"
  - slug: pe-multiple
    name: "P/E Multiple"
    low: 330.00
    mid: 370.00
    high: 410.00
    suitability: 0.70
    suitability_reason: "Mature business but growth premium distorts"

risk_reward:
  risk_to_reward: 2.5
  risk_percentage: 15
  value_at_risk: 1500.00
  value_at_risk_percentage: 15
  kelly_formula: 0.18

market_potential:
  market_size: "$800B cloud + $200B AI services"
  growth_potential_rating: 8
  price_potential_short_term: "Limited upside at current multiple"
  price_potential_two_years: "15-25% if AI monetization thesis plays out"
  price_potential_five_years: "50%+ if Azure maintains 30%+ growth"

likelihood_of_expected_outcomes: "Medium-High"
how_much_already_priced_in: 70
how_much_already_priced_in_reason: "Azure growth largely expected; Copilot upside partially discounted"
```

Maps to `StockValuationResponse`, `StockInvestmentDecision`, `ValuationModel`, `MarketAndPricePotential`, and `InvestmentDecision` from the GraphQL API. Rebuilt when the agent fetches fresh valuation data or the user triggers a refresh.

### `consensus.yaml` — market consensus

Analyst ratings, price targets, and market sentiment — what the market thinks, separate from what the user thinks.

```yaml
symbol: MSFT
updated: "2026-04-15"
validity: point_in_time
half_life_days: 30

ratings:
  consensus: overweight
  buy: 38
  hold: 8
  sell: 2
  average_target: 420.00
  high_target: 480.00
  low_target: 350.00

sentiment:
  community: "Bullish"
  market_outlook: "Cautiously optimistic"
  market_volatility_index: 18.5
  market_environment: "Risk-on with rate cut expectations"

uncertainty: "Moderate — AI investment cycle unclear"
```

Maps to `MarketSentimentAndRisk` and analyst data from the GraphQL API. Useful for comparing user thesis against consensus ("am I contrarian or consensus?").

---

## 6a. Spaces — Research Workspaces

Spaces are long-running research containers that accumulate knowledge over time. A space aggregates conversations, files (PDFs, earnings transcripts), YouTube summaries, web sources, and extracted facts around a topic (e.g., "MSFT valuation", "European defence companies", "AI chip supply chain").

### What a Space is (from GraphQL)

From `Space` in the schema:
- `title`, `description`, `instructions` — what this research is about
- `knowledgeBase` — markdown synthesis of accumulated knowledge
- `knowledgeBaseSources` — source attribution
- `discoverPhaseBase` — grounding context for the discovery phase
- `sources` — uploaded files (PDFs, markdown) stored in S3
- `conversations` — linked chat threads
- `youtubeChannels`, `websites` — monitored sources
- `timingValidity` — time window (ALL_TIME → LAST_MONTH) controlling what's in scope
- `dedicatedMemory` — whether this space has its own isolated memory
- `members` — collaborative access (OWNER, ADMIN, EDITOR, VIEWER)

### Space memory structure

```text
spaces/<space_id>/
  summary.md               # latest synthesis of all space research
  items.yaml               # atomic facts extracted from conversations, files, sources
  knowledge-base.md        # synced from Space.knowledgeBase (the living research doc)
  sources.yaml             # manifest of all sources
  reports/                 # generated reports by style, timestamped
    YYYY-MM-DD-report.md
    YYYY-MM-DD-deep-report.md
    YYYY-MM-DD-key-takeaways.md
    YYYY-MM-DD-blog-post.md
    YYYY-MM-DD-tldr.md
    YYYY-MM-DD-summary.md
```

### `sources.yaml` — source manifest

Tracks all inputs feeding into the space:

```yaml
space_id: "sp-abc123"
title: "MSFT Valuation Deep Dive"
timing_validity: WITHIN_LAST_3_MONTHS
updated: "2026-04-15"

files:
  - url: "s3://spaces/sp-abc123/msft-10k-2025.pdf"
    file_name: "msft-10k-2025.pdf"
    mime_type: "application/pdf"
    file_size: 2450000
  - url: "s3://spaces/sp-abc123/copilot-analysis.md"
    file_name: "copilot-analysis.md"
    mime_type: "text/markdown"
    file_size: 12000

youtube_channels:
  - "UC_x5XG1OV2P6uZZ5FSM9Ttw"    # Google/Alphabet earnings
  - "UCnUYZLuoy1rq1aVMwx4piYg"    # Yahoo Finance

websites:
  - "https://seekingalpha.com/symbol/MSFT"
  - "https://www.microsoft.com/en-us/investor"

conversations:
  - id: "conv-001"
    title: "Initial MSFT valuation discussion"
    date: "2026-04-01"
  - id: "conv-005"
    title: "Post-earnings review"
    date: "2026-04-12"
```

### Space ↔ ticker linking

A space like "MSFT valuation" touches both `spaces/<id>/` and `tickers/MSFT/`. Facts flow between them:

- **Space → Ticker:** Durable facts extracted from space research get written to `tickers/MSFT/items.yaml` with `source_type: space_research` and `source_ref: "space:sp-abc123"`.
- **Ticker → Space:** When synthesizing a space report, the agent reads `tickers/MSFT/summary.md` and `thesis.md` for current context.
- A space can reference multiple tickers (e.g., "European defence" → BAE.L, RHM.DE, SAF.PA).

### `timingValidity` and decay

The space's `timingValidity` enum controls what's in scope for synthesis:

| `timingValidity` | Facts included in synthesis |
|---|---|
| `WITHIN_LAST_MONTH` | Only facts from last 30 days |
| `WITHIN_LAST_3_MONTHS` | Last 90 days |
| `WITHIN_LAST_6_MONTHS` | Last 180 days |
| `WITHIN_LAST_YEAR` | Last 365 days |
| `WITHIN_LAST_5_YEARS` | Last 5 years |
| `WITHIN_ALL_TIME` | Everything |

This acts as a hard filter on top of the decay system — a space scoped to LAST_MONTH won't include a fact from 60 days ago even if it has high access count.

---

## 6b. Report Styles

Spaces generate reports in multiple styles. Each style is a different synthesis of the same underlying data (`items.yaml` + `knowledge-base.md` + conversation history + linked ticker data).

### Available styles

| Style | Slug | Description | Typical length |
|---|---|---|---|
| **Report** | `report` | Comprehensive structured report with sections, data, and analysis. | 2000-5000 words |
| **Deep Report** | `deep-report` | Exhaustive analysis — covers every angle, includes methodology notes, raw data references, and dissenting views. | 5000-10000 words |
| **Key Takeaways** | `key-takeaways` | Bullet-point summary of the most important findings. Decision-focused. | 300-800 words |
| **Blog Post** | `blog-post` | Narrative format, readable by a general audience. Explains context and reasoning. | 1000-2500 words |
| **TLDR** | `tldr` | One-paragraph executive summary. The absolute minimum. | 50-150 words |
| **Summary** | `summary` | Balanced overview — more context than TLDR, less detail than Report. | 500-1500 words |

### Storage

Reports are stored as timestamped files under `reports/`:

```text
spaces/<space_id>/reports/
  2026-04-15-report.md
  2026-04-15-tldr.md
  2026-04-15-key-takeaways.md
  2026-04-08-report.md          # previous week's report
  2026-04-01-summary.md
```

Timestamps create a history — users can see how their research view evolved over time.

### GraphQL mapping

Maps to `SpaceSummary` in the API:

| Report field | `SpaceSummary` field |
|---|---|
| `summary` / `report` / `deep-report` / `blog-post` | `contentMarkdown` / `contentHTML` |
| `tldr` | `tldrMarkdown` / `tldrHTML` |
| `key-takeaways` | `keyTakeawaysMarkdown` / `keyTakeawaysHTML` |

The API currently stores `content`, `tldr`, and `keyTakeaways` per summary. For `report`, `deep-report`, and `blog-post`, these would either:
- Use `contentMarkdown` with a `style` metadata field to distinguish them, or
- Be stored only in the memory layer (files) and synced to the API as the primary `contentMarkdown`.

### When reports are generated

| Trigger | What happens |
|---|---|
| User requests ("give me a report on this space") | Agent generates the requested style from current data |
| Scheduled synthesis (weekly or per `timingValidity`) | Agent generates default style (usually `summary`) |
| Space data changes significantly (new source added, major fact update) | Agent optionally regenerates `key-takeaways` and `tldr` |
| User compares periods ("what changed since last month?") | Agent diffs current vs previous report of same style |

---

## 7. Decay Implementation

### At write time

1. Determine `validity` from fact content:
   - Contains a date/quarter reference → likely `expires`
   - Is a price, ratio, or valuation judgment → `point_in_time`
   - Is a structural/biographical fact → `evergreen`
2. Set `half_life_days` from category defaults (table in section 3) unless user overrides.
3. Set `expires` date if `validity: expires`.

### At read/recall time

1. Compute `decay_score` for each `point_in_time` fact using the half-life formula with access reheat.
2. For `expires` facts, check if `today > expires` → transition to `historical` if not already done.
3. Rank results: `final_score = semantic_score × decay_score` for `point_in_time` facts.
4. `evergreen` and non-expired `expires` facts get `decay_score = 1.0`.
5. `historical` facts get a flat penalty (e.g., `decay_score = 0.3`) — present but deprioritized.

### At synthesis time (weekly or on-demand)

1. Rewrite `summary.md` with Current/Fading/Historical groupings.
2. Rebuild `thesis.md` from current active facts (bull/bear/risks/growth/catalysts/position).
3. Refresh `valuation.yaml` from API if stale (check `updated` date vs half-life).
4. Refresh `consensus.yaml` from API if stale.
5. Transition any `expires` facts past their date to `historical`.
6. Update access metadata for all facts referenced during the week.
7. For spaces: regenerate `summary.md` and default report style, respecting `timingValidity` window.
8. Rewrite `goals/summary.md` from active entries in `goals/items.yaml` (and transition expired or achieved goals as needed).

---

## 8. GraphQL Bridge

Facts from the GraphQL API should be synced into the memory layer. The agent reads from the API when data is missing or stale, and writes back when the user creates/updates content via conversation.

| GraphQL type | Memory file | Sync direction |
|---|---|---|
| `Watchlist` | `watchlists/<id>/items.yaml` | API → memory |
| `StockValuationResponse` | `tickers/<SYMBOL>/valuation.yaml` | API → memory |
| `StockInvestmentDecision` | `tickers/<SYMBOL>/valuation.yaml` + `thesis.md` | API → memory |
| `CompanyOutlook` | `tickers/<SYMBOL>/thesis.md` (risks, growth, uncertainties) | API → memory |
| `InvestmentOpportunity` | `tickers/<SYMBOL>/thesis.md` (short/mid/long term) | API → memory |
| `MarketSentimentAndRisk` | `tickers/<SYMBOL>/consensus.yaml` | API → memory |
| `ValuationModel` | `tickers/<SYMBOL>/valuation.yaml` (models list) | API → memory |
| `MarketAndPricePotential` | `tickers/<SYMBOL>/valuation.yaml` (market_potential) | API → memory |
| `Note` | `tickers/<SYMBOL>/items.yaml` or daily notes | Bidirectional |
| `Space` | `spaces/<id>/sources.yaml` + `knowledge-base.md` | API → memory |
| `SpaceSummary` | `spaces/<id>/reports/YYYY-MM-DD-*.md` | Bidirectional |
| `SpaceSource` | `spaces/<id>/sources.yaml` (files list) | API → memory |

---

## 9. Open Questions

- [ ] Should `half_life_days` be configurable per user (e.g., a day trader wants faster decay than a long-term investor)?
- [ ] How to handle conflicting facts from different sources (agent analysis says bearish, analyst report says bullish)?
- [ ] Should global facts be writable by any user or only by a system/admin agent?
- [ ] Earnings cycle awareness — auto-adjust decay around known earnings dates (e.g., guidance facts get reheat in the week before earnings)?
- [ ] Integration with `qmd` — does `qmd` support custom scoring hooks, or do we apply decay post-retrieval?
- [ ] `valuation.yaml` refresh cadence — how often should the agent pull fresh valuation data from the API vs relying on cached files?
- [ ] Space cross-referencing — when a space touches multiple tickers, should facts be duplicated or use entity references?
- [ ] Report diff generation — should the agent auto-generate diffs between reports of the same style across time periods?
- [ ] `deep-report` and `blog-post` storage — extend `SpaceSummary` API with a `style` field, or store only in the memory layer?
- [ ] Space `dedicatedMemory` — when true, should the space's `items.yaml` be isolated from ticker-level facts, or always cross-pollinate?
- [ ] Goals ↔ API — should portfolio goals sync to a GraphQL type, or stay file-only until a backend exists?
- [ ] `goal_type` enum — extend with tax, ESG, or rebalancing goals as product needs them?
