# 01 — Architecture

## The pipeline

```
  RAW SOURCES                DETERMINISTIC SPINE            NARRATIVE LAYER
  ───────────                ───────────────────            ───────────────

  Kite Connect  ──┐
  (OHLCV, quotes, │
   instruments)   │
                  ├──►  ingest/  ──►  raw tables  ──►  metrics/  ──►  metric_values
  BSE/NSE         │     (idempotent,     (immutable,    (pure fn,      (field_id,
  announcements ──┤      dated,           append-only)   no LLM,        value, as_of,
                  │      retryable)                      tested)        provenance)
  Filings,        │                                          │
  results, ───────┘                                          │
  shareholding                                               ▼
                                                    scoring/ ──► horizon_scores
  ┌──────────────────────────────┐                            │
  │ llm/ (ONLY package that may  │                            │
  │ import anthropic)            │                            ▼
  │                              │                    candidate set (top N)
  │  extract/  filings → typed   │◄───────────────────────────┤
  │            qualitative facts │                            │
  │  compose/  facts + metric    │                            │
  │            tokens → prose    │──────────────►  report assembly
  └──────────────────────────────┘                            │
                                                              ▼
                                                    token substitution
                                                    + validation gate
                                                              │
                                                    ┌─────────┴─────────┐
                                                    │                   │
                                                 PASS                FAIL
                                                    │                   │
                                                    ▼                   ▼
                                            recommendations      cascade_gap
                                            (IMMUTABLE)          (logged, retried,
                                                    │             never shown)
                                                    ▼
                                        sim/ ──► daily marks ──► calibration
```

## Module contracts

### `ingest/`
Pulls raw data, writes it verbatim, never transforms.
- Every job is **idempotent on `(source, entity, as_of)`**. Re-running a day is safe.
- Every job records a `ingest_run` row: started, finished, rows_written, errors.
- Failures are partial-tolerant: one bad symbol does not fail the batch.
- Rate limits respected via a token bucket in Redis. Kite: 3 req/s historical, 1 req/s quote.

### `metrics/`
Pure functions. Input: raw rows. Output: `MetricValue(field_id, value, unit, as_of, inputs_hash)`.
- **No network calls. No LLM. No database writes from inside a metric function** — the
  caller persists. Metrics are testable in isolation with a fixture dataframe.
- Every metric is registered in `docs/06-METRIC-REGISTRY.md` with a stable `field_id`.
- A metric that cannot be computed returns `None` with a `reason` — never a default.

### `scoring/`
Combines metric values into horizon-specific composite scores using declared weights.
Weights live in a versioned YAML (`config/weights.v1.yaml`), not in code, so that
calibration can later tell you which weight-set performs better. Every score records
`weights_version`.

### `llm/`
Two sub-packages, strictly separated:
- `llm/extract/` — reads unstructured text (announcements, concall transcripts, annual
  report sections) and emits **typed structured facts** conforming to a Pydantic schema.
  Output is data, not prose. Cached by content hash.
- `llm/compose/` — takes structured facts + a whitelist of metric tokens and writes the
  report narrative. Output must pass the report contract validator.

### `sim/`
Owns simulated positions and their daily mark-to-market. Also owns calibration scoring.
Runs after EOD ingestion completes, never before.

### `api/`
Thin. Routers call services, services call the modules above. No business logic in routers.

## Request-time vs batch-time

**Batch (nightly, post-close ~16:15 IST onward):**
ingest → metrics → scoring → falsifier checks → sim marks → calibration update

**Batch (on-demand, user-triggered):**
report generation for a specific stock+horizon (LLM calls, 20–60s, streamed)

**Request-time:**
everything else. All reads. Live quotes via Kite websocket proxied through the API.

Rule: the user never waits on an LLM call for a *list*. Lists come from the deterministic
spine, which is precomputed. LLM calls happen only when a specific report is opened.

## Nightly job order (strict)

```
1.  refresh_instruments          (Kite instrument dump)
2.  ingest_ohlcv_daily           (all tracked symbols, adjusted + unadjusted)
3.  ingest_corporate_actions
4.  ingest_announcements
5.  ingest_fundamentals          (when new filings detected)
6.  compute_metrics              (fan-out by symbol, Dramatiq)
7.  compute_scores               (per horizon)
8.  check_falsifiers             ← raises alerts on live theses
9.  mark_simulated_positions
10. score_expired_recommendations
11. update_calibration
```

Each step gates the next. Step 6 does not start until step 2 reports complete for the
trade date. Store a `pipeline_run` row with per-step status so the UI can show
"data current as of" honestly.

## Failure philosophy

- **Missing data is shown, not hidden.** A report with 3 of 12 metrics unavailable renders
  with `—` and a coverage badge. It does not silently degrade.
- **A failed validation is a logged event**, written to `cascade_gap` with the offending
  output, so you can improve the prompt. It is never shown to the user.
- **Stale data blocks recommendations.** If OHLCV is more than 2 trading days behind,
  the research module refuses to score and the UI says so.

## Frontend architecture

- Routes are feature-sliced. `features/planner`, `features/allocation`, `features/equity`,
  `features/simulator`, `features/calibration`.
- Server state exclusively via TanStack Query. No manual fetch in components.
- `packages/contracts` is generated from Pydantic models via `datamodel-code-generator`
  → OpenAPI → `openapi-typescript`. Run on every API change. Types are never hand-written.
- **`src/design/` is the only place a colour, radius, duration, or font is defined.**
  A hex code anywhere else is a bug. Add an ESLint rule for it.
