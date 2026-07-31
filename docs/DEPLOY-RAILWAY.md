# Deploying CORPUS on Railway

One app service built from the repo `Dockerfile` (FastAPI under `/api`,
web bundle at `/`), plus managed **Postgres** and (optionally) **Redis**.

## Services

| Service | Source | Notes |
|---|---|---|
| `corpus` | this repo, Dockerfile builder (`railway.json` pins it) | serves API + web on `$PORT` |
| `postgres` | Railway Postgres plugin | plain Postgres 16 works — the TimescaleDB hypertables are conditional and skip cleanly when the extension is absent |
| `redis` | Railway Redis plugin (optional) | only needed for the Kite login flow and Dramatiq fan-out |

## Environment variables on the `corpus` service

| Variable | Value | Required |
|---|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (service reference) | yes — the app normalises `postgresql://` to `postgresql+asyncpg://` itself |
| `CORPUS_BASIC_AUTH` | `you:a-long-password` | yes — without it the app serves **only** the health check and says why. `off` disables auth explicitly; never do that on a public URL |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` | only for Kite login / Dramatiq |
| `CORPUS_FEED` | `hub` | live layer upstream (`kite` / `replay` / `off`) |
| `WS_HUB_URL` | `wss://ws-hub-production-115e.up.railway.app/<path>` | for `CORPUS_FEED=hub`; inside the same Railway project the private hostname also works |
| `WS_HUB_SUBSCRIBE` | JSON handshake if the hub needs one | optional |
| `CORPUS_SCHEDULER` | `1` | nightly pipeline at 16:15 IST |
| `ANTHROPIC_API_KEY` | your key | for report generation; everything deterministic works without it |
| `KITE_API_KEY` / `KITE_API_SECRET` | your keys | for the Kite login flow + backfill |

Notes:
- Migrations run automatically on every deploy (the container start command
  is `alembic upgrade head && uvicorn ...`).
- Health check is `/api/health` and is the one path exempt from Basic auth.
- The live websocket (`/api/live/ws`) sits behind the same Basic auth,
  including the upgrade request. Browsers reuse cached Basic credentials on
  same-origin websocket upgrades; if a browser refuses, the page still works
  fully minus live ticks (the client retries with backoff).

## Path A — deployed by Claude Code (from a session)

The session needs two things it does not have by default:

1. **Egress**: add `railway.app`, `railway.com`, and `backboard.railway.app`
   to the environment's allowed network hosts. Policy applies to **new**
   sessions only — start a fresh session after changing it.
2. **Auth**: create a token at railway.app → Account → Tokens. A
   **team token for the `nbothra` workspace** scopes the deploy to the right
   place. Add it as environment variable `RAILWAY_API_TOKEN` in the Claude
   Code environment settings (not pasted into chat).

Then, in the fresh session, deploying is:

```sh
npm i -g @railway/cli   # or: curl -fsSL https://railway.com/install.sh | sh
railway init --name corpus            # team is implied by the team token
railway add --database postgres
railway add --database redis          # optional
railway up --detach                   # builds the Dockerfile, deploys
railway variables --set "CORPUS_BASIC_AUTH=you:…" --set "CORPUS_FEED=hub" \
  --set "WS_HUB_URL=wss://ws-hub-production-115e.up.railway.app/…" \
  --set "CORPUS_SCHEDULER=1" --set 'DATABASE_URL=${{Postgres.DATABASE_URL}}'
railway domain                        # mint the public URL
```

## Path B — deployed by you, locally

Same commands, after `railway login` (browser flow) — run them from the
repo root and pick the `nbothra` workspace when `railway init` asks.

## After the first deploy

1. Open the public URL — the browser prompts for the Basic auth credentials.
2. `/api/live/status` should show the hub feed CONNECTED (or say exactly
   why not).
3. Complete the profile in the planner, set allocation preferences, and —
   once Kite keys are in — log in via `/api/auth/kite/login` and run the
   backfill so the metric spine fills.
