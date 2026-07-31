# CORPUS — Claude Code Operating Manual

> Rename `CORPUS` to whatever you want later. It's used as the package namespace throughout.

This is a **single-user personal investment research system** for Indian markets.
Not a product. Not multi-tenant. No auth beyond a local session. No compliance layer.
Optimise for correctness, traceability, and speed of iteration — not for scale.

---

## The one rule that governs everything

**A number the user sees must be traceable to a deterministic computation or a raw source record.**

The LLM never produces numbers. The LLM reads, reasons qualitatively, and writes prose
around numbers that the Python layer already computed. Enforcement is mechanical, not
by prompt discipline — see `docs/07-REPORT-CONTRACT.md`.

If you are ever about to write code where a model output flows directly into a
displayed figure, stop. That is the failure mode this entire architecture exists to prevent.

---

## Second rule: every recommendation is a falsifiable, scored bet

No recommendation ships without:
1. A horizon (SHORT / MID / LONG)
2. A scenario band (bear / base / bull), never a point prediction
3. At least one **falsifier** — a machine-checkable condition that kills the thesis
4. An immutable snapshot written to `recommendations` at issue time

When the horizon expires, the system scores itself. See `docs/08-SIMULATOR-AND-CALIBRATION.md`.
The calibration numbers are shown to the user prominently, including when they're bad.
Especially when they're bad.

---

## Stack (locked — do not substitute)

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic |
| DB | PostgreSQL 16 + TimescaleDB extension |
| Cache / broker | Redis 7 |
| Jobs | APScheduler in-process for cron; Dramatiq + Redis for fan-out ingestion |
| Market data | Kite Connect (`kiteconnect` python SDK) |
| LLM | Anthropic API (`anthropic` python SDK), `claude-sonnet-4-6` for extraction, `claude-opus-4-6`-class for synthesis |
| Frontend | React 19 + TypeScript + Vite |
| State | TanStack Query (server), Zustand (client) |
| Styling | Tailwind v4 with a **custom token layer only** — default palette disabled |
| Motion | `motion` (Framer Motion v11+) |
| Price charts | `lightweight-charts` (TradingView) |
| Analytic charts | `visx` + d3-scale |
| 3D | `three` + `@react-three/fiber` + `@react-three/drei` — two places only |
| Tests | `pytest` + `pytest-asyncio`, `vitest`, `playwright` |

Package manager: `uv` for Python, `pnpm` for JS. Monorepo, no workspace magic beyond
`apps/api`, `apps/web`, `packages/contracts`.

---

## Repo layout

```
corpus/
├── CLAUDE.md
├── docs/                        ← read these before writing code
├── apps/
│   ├── api/
│   │   └── corpus/
│   │       ├── ingest/          ← Kite + filings + announcements
│   │       ├── metrics/         ← deterministic computation. NO LLM IMPORTS ALLOWED.
│   │       ├── planner/         ← cashflow + constraint engine
│   │       ├── allocation/      ← asset-class suitability
│   │       ├── research/        ← equity scoring + report assembly
│   │       ├── llm/             ← the only package permitted to import `anthropic`
│   │       ├── sim/             ← paper positions + calibration
│   │       ├── api/             ← FastAPI routers
│   │       └── db/              ← models, migrations, session
│   └── web/
│       └── src/
│           ├── design/          ← tokens, primitives. Nothing else defines a colour.
│           ├── features/
│           └── routes/
└── packages/contracts/          ← shared TS types generated from Pydantic
```

**Architectural fence, enforced in CI:** `corpus/metrics/**` may not import `corpus.llm`
or `anthropic`. Add a test that greps for it. This is the boundary that keeps the system honest.

---

## Reading order for docs

| File | What it locks down |
|---|---|
| `docs/00-PRODUCT-BRIEF.md` | What this is, what it refuses to do |
| `docs/01-ARCHITECTURE.md` | Modules, data flow, the pipeline |
| `docs/02-DATA-LAYER.md` | Schema, Kite integration, ingestion jobs |
| `docs/03-PLANNER-ENGINE.md` | Pre-investment financial planning |
| `docs/04-ALLOCATION-ENGINE.md` | Asset-class ranking / suitability |
| `docs/05-EQUITY-RESEARCH-ENGINE.md` | Stock scoring by horizon |
| `docs/06-METRIC-REGISTRY.md` | The canonical field-ID list |
| `docs/07-REPORT-CONTRACT.md` | How the LLM is caged |
| `docs/08-SIMULATOR-AND-CALIBRATION.md` | Paper trading + self-scoring |
| `docs/09-DESIGN-SYSTEM.md` | Full visual spec — read before ANY UI work |
| `docs/10-BUILD-ORDER.md` | Milestones + acceptance criteria |

---

## Working conventions

- **Migrations**: every schema change gets an Alembic revision in the same commit. No exceptions.
- **Money**: `Decimal` in Python, `NUMERIC(18,4)` in Postgres, integer paise in JSON transport.
  Never float. Never.
- **Dates**: all market data keyed by `trade_date` (IST calendar date), not timestamps.
  Store the NSE trading-holiday calendar; don't infer it.
- **Timezone**: everything internal is UTC; render in `Asia/Kolkata`.
- **Nulls**: a missing metric is `None` and renders as `—`. Never zero-fill. Never impute silently.
- **Provenance**: every metric row carries `source`, `as_of`, `computed_at`. The UI shows it.
- **Tests**: any function in `metrics/` gets a golden-value test with a hand-checked fixture.

## When you're unsure

Prefer the boring, inspectable implementation. This system's value is that its owner can
audit why it said what it said. A clever unexplainable improvement is a regression.
