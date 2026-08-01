"""initial schema — spec §4

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-01

"""
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

DDL = """
-- ---------- accounts / tenancy ----------
CREATE TABLE account (
  id              BIGSERIAL PRIMARY KEY,
  slug            TEXT UNIQUE NOT NULL,          -- 'memes', 'finance', 'facts'
  niche           TEXT NOT NULL,
  display_name    TEXT NOT NULL,
  ig_user_id      TEXT,
  yt_channel_id   TEXT,
  posts_per_day   INT NOT NULL DEFAULT 3,
  active          BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- trend ingest ----------
CREATE TABLE trend_signal (
  id            BIGSERIAL PRIMARY KEY,
  source        TEXT NOT NULL,
  external_id   TEXT NOT NULL,
  topic_raw     TEXT NOT NULL,
  topic_norm    TEXT NOT NULL,
  niche         TEXT,
  metric_value  NUMERIC,
  observed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  raw           JSONB NOT NULL,
  CONSTRAINT uq_signal UNIQUE (source, external_id, observed_at)
);
CREATE INDEX ix_signal_topic_time ON trend_signal (topic_norm, observed_at DESC);
CREATE INDEX ix_signal_source_time ON trend_signal (source, observed_at DESC);

CREATE TABLE trend (
  id             BIGSERIAL PRIMARY KEY,
  topic_norm     TEXT NOT NULL,
  topic_display  TEXT NOT NULL,
  niche          TEXT NOT NULL,
  velocity_6h    NUMERIC NOT NULL DEFAULT 0,
  velocity_24h   NUMERIC NOT NULL DEFAULT 0,
  breadth        INT NOT NULL DEFAULT 0,
  intensity      NUMERIC NOT NULL DEFAULT 0,
  phase          TEXT NOT NULL DEFAULT 'emerging',   -- emerging|peaking|decaying
  first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  used_count     INT NOT NULL DEFAULT 0,
  CONSTRAINT uq_trend UNIQUE (topic_norm, niche)
);
CREATE INDEX ix_trend_phase ON trend (niche, phase, intensity DESC);

-- ---------- content generation ----------
CREATE TABLE format_skeleton (
  id            BIGSERIAL PRIMARY KEY,
  trend_id      BIGINT REFERENCES trend(id) ON DELETE CASCADE,
  skeleton      JSONB NOT NULL,
  model         TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE script_draft (
  id            BIGSERIAL PRIMARY KEY,
  account_id    BIGINT NOT NULL REFERENCES account(id),
  trend_id      BIGINT NOT NULL REFERENCES trend(id),
  skeleton_id   BIGINT NOT NULL REFERENCES format_skeleton(id),
  template_key  TEXT NOT NULL,
  beats         JSONB NOT NULL,
  caption       TEXT NOT NULL,
  hashtags      TEXT[] NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE render_job (
  id            BIGSERIAL PRIMARY KEY,
  script_id     BIGINT NOT NULL REFERENCES script_draft(id),
  status        TEXT NOT NULL DEFAULT 'queued',  -- queued|running|done|failed
  output_path   TEXT,
  duration_ms   INT,
  error         TEXT,
  attempts      INT NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at   TIMESTAMPTZ
);
CREATE INDEX ix_render_status ON render_job (status, created_at);

-- ---------- assets ----------
CREATE TABLE asset (
  id            BIGSERIAL PRIMARY KEY,
  source        TEXT NOT NULL,      -- pexels|pixabay|own
  external_id   TEXT,
  local_path    TEXT NOT NULL,
  duration_ms   INT,
  width         INT,
  height        INT,
  tags          TEXT[],
  license       TEXT NOT NULL,
  license_url   TEXT,
  qdrant_id     TEXT,
  use_count     INT NOT NULL DEFAULT 0,
  last_used_at  TIMESTAMPTZ,
  CONSTRAINT uq_asset UNIQUE (source, external_id)
);
CREATE INDEX ix_asset_use ON asset (use_count ASC, last_used_at ASC NULLS FIRST);

-- ---------- publishing ----------
CREATE TABLE post (
  id              BIGSERIAL PRIMARY KEY,
  account_id      BIGINT NOT NULL REFERENCES account(id),
  render_job_id   BIGINT NOT NULL REFERENCES render_job(id),
  platform        TEXT NOT NULL,           -- instagram|youtube
  platform_id     TEXT,
  slot            SMALLINT NOT NULL,       -- 0..9
  status          TEXT NOT NULL DEFAULT 'pending_qc',
                  -- pending_qc|approved|rejected|scheduled|published|failed
  scheduled_for   TIMESTAMPTZ,
  published_at    TIMESTAMPTZ,
  caption         TEXT,
  error           TEXT
);
CREATE INDEX ix_post_status ON post (status, scheduled_for);

CREATE TABLE post_insight (
  id            BIGSERIAL PRIMARY KEY,
  post_id       BIGINT NOT NULL REFERENCES post(id) ON DELETE CASCADE,
  collected_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  impressions   BIGINT,
  reach         BIGINT,
  saves         BIGINT,
  shares        BIGINT,
  comments      BIGINT,
  likes         BIGINT,
  watch_pct     NUMERIC,
  reward        NUMERIC   -- computed, see spec §9
);

-- ---------- bandit state ----------
CREATE TABLE slot_stat (
  id            BIGSERIAL PRIMARY KEY,
  account_id    BIGINT NOT NULL REFERENCES account(id),
  slot          SMALLINT NOT NULL,
  dow           SMALLINT NOT NULL,     -- 0=Mon
  alpha         NUMERIC NOT NULL DEFAULT 1.0,
  beta          NUMERIC NOT NULL DEFAULT 1.0,
  n             INT NOT NULL DEFAULT 0,
  CONSTRAINT uq_slot UNIQUE (account_id, slot, dow)
);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS slot_stat;
        DROP TABLE IF EXISTS post_insight;
        DROP TABLE IF EXISTS post;
        DROP TABLE IF EXISTS asset;
        DROP TABLE IF EXISTS render_job;
        DROP TABLE IF EXISTS script_draft;
        DROP TABLE IF EXISTS format_skeleton;
        DROP TABLE IF EXISTS trend;
        DROP TABLE IF EXISTS trend_signal;
        DROP TABLE IF EXISTS account;
        """
    )
