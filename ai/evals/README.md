# Evals: DeepEval + Langfuse

Offline-first checks live in `pytest` under `tests/` (default: **no network**). This folder holds the **golden financial Q&A set** and runbooks for deeper evals.

## Golden set

- **File:** `financial_qa_golden.yaml`
- **Gate:** `tests/test_financial_golden_schema.py` validates structure (≥20 cases, tiers, tags).

Each case includes `route`, `mode`, capabilities, tool/source hints, `forbidden` behaviors, and either `rubric` or `expected_substrings` for assertion-style metrics.

## Eval and test tiers (Phase 22)

| Tier | Name | Network | Typical duration | Default CI | Purpose |
|------|------|---------|-----------------|------------|---------|
| **T0** | Unit / contract | **No** | seconds | **Yes** | Schemas, routes, auth, mocked providers, loader/schema tests for `financial_qa_golden.yaml` |
| **T1** | Integration (offline) | **No** | seconds–minute | **Yes** | Deeper in-process flows with fakes: full prompt stack to stub LLM, WS envelope round-trips |
| **T2** | Slow / heavy offline | **No** (or localhost) | minutes | **No** (`@pytest.mark.slow`) | Large parametrized cases, property tests, full golden subset without API |
| **T3** | Live / API eval | **Yes** (LLM or search) | minutes+ | **No** (`@pytest.mark.live` + env flag) | DeepEval against real model; FinanceBench full run |
| **T4** | Manual / exploratory | n/a | n/a | **No** | Ad hoc runs documented here only; not machine-gated |

**T0 is the landing bar for every PR.** T2–T3 are opt-in unless policy moves them to a scheduled job.

### pytest markers

| Marker | Tier | Excluded from default? |
|--------|------|----------------------|
| _(none)_ | T0 / T1 | Never excluded |
| `slow` | T2 | Yes — excluded by `-m "not slow and not live"` |
| `live` | T3 | Yes — also requires `AI_HARNESS_LIVE_EVAL=1` |

### Gate vocabulary

| Gate | When | Command |
|------|------|---------|
| **Local dev** | While editing | `uv run pytest` (T0 default) or targeted path |
| **Pre-push** | Before sharing branch | `uv run pytest -m "not slow and not live"` |
| **Landing** | Before merge to main | Same as pre-push; add T2 locally if eval-sensitive code changed |
| **CI** | On PR | At minimum T0; T1 if fast enough |
| **Nightly / scheduled** | Optional | T2 + T3 with secrets in CI vault |

### Commands

**Default CI / local (T0 + T1):**

```bash
cd ai
uv run pytest -m "not slow and not live"
```

**Include slow / T2:**

```bash
uv run pytest                       # all except @pytest.mark.live
uv run pytest -m slow               # only slow tests
```

**Live eval / T3 (opt-in, secrets required):**

```bash
export AI_HARNESS_LIVE_EVAL=1
uv run pytest -m live
```

### Environment variables for tier gates

| Variable | Tier | Description |
|----------|------|-------------|
| `AI_HARNESS_LIVE_EVAL` | T3 | Set to `1` to enable live/API tests |
| `FINANCEBENCH_DATA_DIR` | T3 | Path to FinanceBench JSONL data; see `evals/financebench/README.md` |
| `RUN_FINANCEBENCH` | T3 | Set to `1` to enable full FinanceBench eval suite |

## DeepEval (offline metric smoke)

Project dev dependency includes `deepeval`. Minimal offline metric example:

```bash
cd ai
uv run pytest tests/test_evals_smoke.py -q
```

For dataset-driven runs (may call models depending on metrics), see [DeepEval docs](https://docs.confident-ai.com/).

## Langfuse (traces)

Langfuse complements pytest asserts: latency, spans, prompt/response logging. It does **not** replace golden YAML or offline metrics.

**Env vars** (optional — app no-ops when unset):

| Variable | Purpose |
|----------|---------|
| `LANGFUSE_PUBLIC_KEY` | Public key |
| `LANGFUSE_SECRET_KEY` | Secret key |
| `LANGFUSE_HOST` | Default `https://cloud.langfuse.com` |

After configuring keys, run the app and complete a chat; open the Langfuse project to inspect traces. Tests use mocks in `tests/test_telemetry_smoke.py` so CI stays offline.

## Sentry + PostHog

See `tests/test_telemetry_smoke.py`. Initialization is optional when `SENTRY_DSN` / `POSTHOG_API_KEY` are absent.
