# CORPUS

Personal investment research system for Indian markets.
Measurement over prediction. Every output is scored.

## Running it locally

### The short version

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1    # Windows
```

```bash
./scripts/setup.sh                                            # macOS / Linux
```

Checks every prerequisite, prepares `.env`, starts a database if Docker is
available, applies migrations, and prints the two commands that start the app.
Safe to re-run. When something is missing it names that one thing and how to
install it, rather than failing several steps later.

The rest of this section is what the script does, by hand.

Two paths. Docker is one command and gets you Postgres and Redis for free;
the native path is better if you want reload-on-save without container churn.

Neither path needs Kite or Anthropic credentials. Without them you get the full
deterministic system — planner, allocation, simulator, calibration — plus a
replay feed of demo ticks. Market ingestion and LLM reports are the only things
that stay switched off, and each says so on screen rather than failing silently.

### Option A — Docker

Requires Docker Desktop (or any Docker Engine) **actually running**:
`docker info` must print a Server section. If it errors with
`Cannot connect to the Docker daemon`, start Docker first — this is the most
common reason the stack won't come up.

```bash
cp .env.example .env          # optional; defaults work without it
CORPUS_FEED=replay docker compose up --build
```

First build takes a few minutes. Migrations run automatically on API boot.

### Option B — Natively

Needs [`uv`](https://docs.astral.sh/uv/), Node 22+, pnpm, and your own
PostgreSQL 16. `uv` fetches Python 3.12 itself, so you do not need it
preinstalled.

Two things are optional despite appearing in `.env.example`:

- **Redis** — only the Kite login token store and the Dramatiq fan-out use it.
  The planner, allocation, simulator, calibration and the replay feed all run
  without it. Skip it until you wire up Kite.
- **TimescaleDB** — the migrations detect it and fall back to plain tables.

```bash
# 1. database (once)
createdb corpus
psql -c "CREATE ROLE corpus LOGIN PASSWORD 'corpus'; ALTER DATABASE corpus OWNER TO corpus;"

# 2. config
cp .env.example .env          # then set CORPUS_FEED=replay for demo ticks

# 3. API — from apps/api, which is where pyproject.toml and alembic.ini live
cd apps/api
uv sync
uv run alembic upgrade head
uv run uvicorn corpus.api.main:app --reload --port 8000

# 4. web — in a second terminal, from the repo root
pnpm install
pnpm dev
```

### On Windows

The commands above are the same, with three differences worth knowing before
you start.

**`&&` does not chain commands in Windows PowerShell 5.1** — the one that opens
as "Windows PowerShell" and ships with the OS. It fails with
`The token '&&' is not a valid statement separator in this version`. Use `;`,
or just run the lines one at a time. PowerShell 7+ (`pwsh`) accepts `&&`.

**Install `uv` first**, then open a new terminal so the updated PATH is picked
up — `uv` stays "not recognized" in the shell you installed from:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

It lands in `%USERPROFILE%\.local\bin`. Confirm with `uv --version` in the new
terminal before going on.

**pnpm** comes from Node's bundled corepack: `corepack enable`.

Then, from the repo root:

```powershell
Copy-Item .env.example .env   # then set CORPUS_FEED=replay
cd apps\api
uv sync
uv run alembic upgrade head
uv run uvicorn corpus.api.main:app --reload --port 8000
```

**PostgreSQL** is the one service you do need. Two ways:

*Docker, if you have it* — brings up only the database, already configured with
the user, password and database name the default `DATABASE_URL` expects, so
there is nothing to edit:

```powershell
docker compose up -d db
```

*Or the [EnterpriseDB installer](https://www.postgresql.org/download/windows/)* —
it does not put `psql` on your PATH, and it creates neither the role nor the
database, so make them once. It will prompt for the `postgres` password you
chose during setup:

```powershell
& 'C:\Program Files\PostgreSQL\16\bin\psql.exe' -U postgres -c "CREATE ROLE corpus LOGIN PASSWORD 'corpus';"
& 'C:\Program Files\PostgreSQL\16\bin\psql.exe' -U postgres -c "CREATE DATABASE corpus OWNER corpus;"
```

A plain `LOGIN` role is enough — the migrations need no superuser rights when
TimescaleDB is absent, which it is on a stock Windows install.

**Redis** has no supported native Windows build — skip it, per the note above,
or use Docker or WSL2 once you actually need the Kite feed.

### What you should see

| URL | |
|---|---|
| http://localhost:5173 | the app — planner, allocation, equity, simulator, calibration, alerts |
| http://localhost:5173/kitchen-sink | design-system reference (docs/09) |
| http://localhost:8000/docs | API explorer |
| http://localhost:8000/health | `{"status":"ok","service":"corpus-api"}` |
| http://localhost:8000/live/status | which feed is running, and why |

The web dev server proxies `/api/*` to the API, websockets included, so the
browser only ever talks to port 5173.

### If it doesn't come up

- **`Cannot connect to the Docker daemon`** — Docker isn't running. See above.
- **`The token '&&' is not a valid statement separator`** — Windows PowerShell
  5.1. Run the lines one at a time, or separate them with `;`.
- **`uv` / `pnpm` is not recognized** — not installed, or installed in a shell
  whose PATH predates it. Open a new terminal and check `uv --version` first.
- **`ConnectionRefusedError: [WinError 1225]`**, or `connection refused` on
  `alembic upgrade head` — nothing is listening on 5432. PostgreSQL isn't
  running; see the Windows section above. The traceback ends in asyncpg and
  mentions SSL, but the cause is just the absent server.
- **API exits with a connection error** — same thing, or `DATABASE_URL` points
  somewhere else. Check `pg_isready` first. Redis is not needed unless you are
  using the Kite feed or the Dramatiq ingestion fan-out.
- **`.env` seems to be ignored** — it is read from the **repo root**, not from
  `apps/api`. From `apps/api`, run
  `uv run python -c "from corpus.config import get_settings; print(get_settings().database_url)"`
  to see what actually loaded.
- **Live tiles say the feed is off** — that's `CORPUS_FEED=off`, the default.
  Set `CORPUS_FEED=replay` for demo ticks; `kite` needs the daily login.
- **Screens are empty of market data** — expected on a fresh database. The
  deterministic engines work from your own inputs; price and fundamentals data
  arrives via the M1 backfill, which needs Kite credentials.

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
