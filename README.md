# CORPUS

Personal investment research system for Indian markets.
Measurement over prediction. Every output is scored.

## Getting started with Claude Code

Drop this whole folder in as your repo root, then open Claude Code and paste:

```
Read CLAUDE.md and every file in docs/ before writing any code.
Then build M0 from docs/10-BUILD-ORDER.md.

Do not skip ahead. Do not start M1 until M0's acceptance criterion passes,
including the architectural fence test.

When M0 is done, show me the acceptance evidence and stop.
```

Then per milestone:

```
M0 passed. Read docs/10-BUILD-ORDER.md M1 and docs/02-DATA-LAYER.md.
Build M1. My Kite credentials are in .env as KITE_API_KEY / KITE_API_SECRET.
Backfill must be resumable — it will crash partway and I don't want to restart it.
Stop at the acceptance criterion.
```

For UI work, always:

```
Read docs/09-DESIGN-SYSTEM.md in full first. Build <screen>.
Then screenshot it with Playwright at 1440 / 768 / 390 in both themes,
show me the screenshots, and critique your own work against the doc
before I look at it.
```

## Structure

```
CLAUDE.md              operating manual, read automatically by Claude Code
docs/00                what this is and refuses to be
docs/01                architecture and pipeline
docs/02                schema, Kite integration, ingestion
docs/03                planner — build this first, it's useful alone
docs/04                allocation engine
docs/05                equity research engine
docs/06                metric registry — the canonical field list
docs/07                report contract — how the LLM is caged
docs/08                simulator + calibration ledger
docs/09                design system — read before any UI
docs/10                build order with acceptance criteria
```

## The three ideas worth remembering

1. **The LLM never emits a number.** It writes `{{fin.roce_median_5y}}`; the renderer
   substitutes. A regex rejects any bare numeral. This is structural, not prompt-based.

2. **Every thesis carries a machine-checkable kill condition.** Falsifiers are evaluated
   nightly. Thesis-breakage alerts, not price alerts.

3. **The calibration ledger is built before the recommendation engine.** The system
   publishes its own hit rate by horizon, including the horizons where it's bad.

## Assumption files you will edit constantly

```
config/assumptions.v1.yaml    return, inflation, tax drag assumptions
config/vehicles.v1.yaml       investment vehicle characteristics
config/weights.v1.yaml        horizon scoring weights
```

Bump the version rather than editing in place. Every recommendation records which
version produced it, which is what makes the calibration comparison meaningful.
