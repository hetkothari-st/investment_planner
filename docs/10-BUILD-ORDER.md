# 10 — Build Order

Ten milestones. Each has a hard acceptance criterion. **Do not start a milestone until
the previous one passes its criterion.** The ordering is deliberate and the unintuitive
parts are the important ones.

The two orderings that matter most:
- **M4 (simulator + calibration) ships before M6 (LLM reports).** Every recommendation the
  system has ever made is then scored from the first one. If you build reports first,
  you'll have months of unscored output and no way to know if any of it was good.
- **The design system (M2) ships before any feature UI.** Retrofitting a visual identity
  onto built screens produces exactly the generic result you're trying to avoid.

---

## M0 — Skeleton
Monorepo, Docker Compose (Postgres+Timescale, Redis), FastAPI boots, Vite boots,
Alembic wired, `uv` and `pnpm` locked, CI running lint + tests.

Also: the architectural fence test.
```python
def test_metrics_never_imports_llm():
    for f in Path("corpus/metrics").rglob("*.py"):
        src = f.read_text()
        assert "anthropic" not in src and "corpus.llm" not in src
```

**Accept:** `docker compose up` → both apps serve; CI green; fence test passes.

---

## M1 — Data spine
Kite auth flow, instrument sync, OHLCV backfill (10y, Nifty 500), trading calendar,
corporate actions, adjusted close computation, `ingest_run` logging, resumable
`scripts/backfill.py`.

**Accept:** 10 years of adjusted daily data for 500 symbols, zero gaps on trading days.
Re-running any single day changes zero rows (idempotency proved by row-hash comparison).

---

## M2 — Design system
`src/design/` tokens, both themes, three fonts loaded and subset, all primitives from the
component inventory, and a `/kitchen-sink` route rendering every primitive in every state.

**Accept:** kitchen-sink screenshot at 1440px, 768px and 390px, in both themes, both
motion settings. Contrast audit passes. No hex outside `src/design/`.

Build the **Calibration Dial** here too, driven by mock data. It's the hardest visual
element and doing it early sets the quality bar for everything after.

---

## M3 — Planner
Profile intake (scenario-based temperament elicitation, not sliders), the gate waterfall,
buffer sizing, debt hurdle, horizon rule, sensitivity table, `plan_versions` persistence.

**Accept:** all five golden cases from `docs/03` pass. A profile with an unfunded emergency
buffer produces zero investable and the allocation route renders locked with the reason.

*This milestone alone is already useful. Live with it for a week before continuing.*

---

## M4 — Simulator + calibration ledger
Simulated positions with full cost model, frozen thesis snapshots, daily marking,
benchmark comparison, XIRR, the calibration schema, scoring job, sample gating, and the
dial wired to real data.

At this point there are no recommendations yet — so seed the ledger with **manually entered
theses**. Type in your own picks with bands and falsifiers. The system starts grading you
before it grades itself, which is a genuinely useful calibration exercise.

**Accept:** open → 30 marks → close reconciles to the paise against a hand-computed
fixture. Regenerating a report leaves `thesis_snapshot_md` byte-identical.

---

## M5 — Metrics + scoring
Every `field_id` in `docs/06`, each pure and golden-tested. Percentile normalisation,
sector bucketing, coverage computation, `metric_gaps` writing, the three weight sets,
composite scoring, cost hurdle, scenario bands from empirical quantiles, correlation prune.

Still no LLM. Still no reports.

**Accept:** run for a historical date 2 years back; the candidate set is reproducible
byte-for-byte across runs. Bands satisfy bear < base < bull for all 500 symbols.
Every generated recommendation carries ≥1 falsifier or the run fails.

---

## M6 — Equity screens + reports
Market overview, symbol page, horizon selector, candidate list, and the LLM layer:
extraction pipeline with verbatim-span validation, composition with the token whitelist,
the validation gate, provenance labels in the rendered report.

**Accept:** 20 consecutive report generations, zero bare numerals in output, zero
unknown tokens. Deliberately break the prompt and confirm the failure renders as a
metrics-only report and writes a `cascade_gap` row.

---

## M7 — Allocation engine + 3D scatter
Vehicle config, hard gates, suitability scoring, bucket-filling allocation, gated-out
explanations, the orthographic 3D scatter with its 2D fallback table.

**Accept:** a 6-month-horizon profile never receives an equity line. Every vehicle is
reachable by some profile. The scatter's 2D table matches the 3D positions exactly.

---

## M8 — Falsifier monitoring + alert centre
Nightly falsifier evaluation, breach detection, thesis-invalidation flow, alert centre
that shows the *original thesis line* each breach contradicts.

**Accept:** synthetically breach a falsifier; the alert appears with the correct quoted
thesis line, the recommendation flips to `INVALIDATED`, and the linked position is
flagged but not auto-closed.

---

## M9 — Live layer
Kite websocket proxy, live indices, movers, the market-overview animation pass.

Deliberately last. It's the most visible and the least valuable. Doing it earlier is the
trap — it's fun to build and it makes the app *look* finished while the parts that
determine whether it's any good are still missing.

**Accept:** websocket survives a 30-minute session with reconnect on drop; no credentials
reach the browser.

---

## Deferred — F&O

Not until M9 is done and you have ≥100 scored equity recommendations. Reasons:

- Options need an entirely separate spine: IV surface, Greeks, term structure, OI,
  payoff modelling, margin. It's a bigger module than everything above it.
- The cost/tax model is different and harsher.
- Most importantly: **if the calibration ledger shows the system is bad at short-horizon
  equity calls, it will be worse at options**, and you'll have learned that for the price
  of some backfill rather than real money.

Let the calibration data decide whether F&O gets built at all. That is the entire point
of building the ledger first.

---

## Per-milestone ritual

1. Write the acceptance test before the implementation.
2. Build.
3. Playwright screenshot every new screen; look at it against `docs/09`; remove one thing.
4. Update the doc if reality diverged from the spec — the docs are the contract, so a
   stale doc is a broken contract.
5. Tag the commit `m<N>-accept`.
