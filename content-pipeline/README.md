# content-pipeline

Autonomous social content pipeline (Phase 1: trend ingest). See
`CONTENT_PIPELINE_BUILD_SPEC.md` (uploaded spec) for the full phase-gated plan.

## Phase 1 status

Implemented: repo structure (spec §2), Alembic revision `0001_initial` (spec §4),
ingest layer with 4 sources + batched LLM niche classification (spec §5).
Later-phase directories (`generate/`, `render/`, `publish/`, `qc/`, `insights/`,
`assets/`) are structural stubs only.

## Setup

```bash
cd content-pipeline
cp .env.example .env          # fill in keys
docker compose up -d          # postgres 16, redis 7, qdrant
uv venv && uv pip install -e ".[dev]"
uv run alembic upgrade head
```

## Run ingest

```bash
uv run python -m src.ingest.runner
```

Each source failing (missing key, API down) is non-fatal — logged and skipped.
Signals land in `trend_signal` with `observed_at` truncated to the minute, so a
re-run within the same minute dedupes on `uq_signal` (ON CONFLICT DO NOTHING).

Niche classification is a single batched Anthropic call per run, cached in Redis
by `topic_norm` for 7 days (`src/ingest/niche.py`). Model is configurable via
`NICHE_MODEL` (default `claude-opus-5`).

## Tests

```bash
uv run pytest
```

`test_ingest_dedup.py` needs a migrated Postgres at `DATABASE_URL`; it skips
itself otherwise.

## Hard constraints (spec §1.1)

- No downloading of third-party social video, ever. Ingest is metadata-only.
  `tests/test_no_forbidden_imports.py` greps for `yt_dlp` / `instaloader` /
  `selenium` / `playwright` in `src/`.
- The TikTok Creative Center endpoint is undocumented and unverified — treated
  as best-effort; failures are logged and skipped.
