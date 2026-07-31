"""data spine: instruments, calendar, ohlcv, corporate actions, ingest_run

Revision ID: 0001
Revises:
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timescale_available(bind) -> bool:
    if bind.dialect.name != "postgresql":
        return False
    row = bind.execute(
        sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb'")
    ).scalar()
    return row is not None


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("instrument_token", sa.BigInteger(), primary_key=True),
        sa.Column("tradingsymbol", sa.Text(), nullable=False),
        sa.Column("exchange", sa.Text(), nullable=False),
        sa.Column("name", sa.Text()),
        sa.Column("isin", sa.Text()),
        sa.Column("segment", sa.Text()),
        sa.Column("lot_size", sa.Integer()),
        sa.Column("tick_size", sa.Numeric(10, 4)),
        sa.Column("expiry", sa.Date()),
        sa.Column("instrument_type", sa.Text()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("tradingsymbol", "exchange", name="uq_instruments_tradingsymbol"),
    )

    op.create_table(
        "companies",
        sa.Column("isin", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("sector", sa.Text()),
        sa.Column("industry", sa.Text()),
        sa.Column("mcap_band", sa.Text()),
        sa.Column("incorporated", sa.Date()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "mcap_band IN ('LARGE','MID','SMALL','MICRO')",
            name="ck_companies_mcap_band_valid",
        ),
    )

    op.create_table(
        "universe_membership",
        sa.Column(
            "isin",
            sa.Text(),
            sa.ForeignKey("companies.isin", name="fk_universe_membership_isin_companies"),
            primary_key=True,
        ),
        sa.Column("index_name", sa.Text(), primary_key=True),
        sa.Column("from_date", sa.Date(), primary_key=True),
        sa.Column("to_date", sa.Date()),
    )

    op.create_table(
        "trading_calendar",
        sa.Column("trade_date", sa.Date(), primary_key=True),
        sa.Column("exchange", sa.Text(), nullable=False, server_default="NSE"),
        sa.Column("is_trading_day", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text()),
    )

    op.create_table(
        "ohlcv_daily",
        sa.Column("instrument_token", sa.BigInteger(), primary_key=True),
        sa.Column("trade_date", sa.Date(), primary_key=True),
        sa.Column("open", sa.Numeric(18, 4)),
        sa.Column("high", sa.Numeric(18, 4)),
        sa.Column("low", sa.Numeric(18, 4)),
        sa.Column("close", sa.Numeric(18, 4)),
        sa.Column("volume", sa.BigInteger()),
        sa.Column("adj_close", sa.Numeric(18, 4)),
        sa.Column("source", sa.Text(), nullable=False, server_default="kite"),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "corporate_actions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("isin", sa.Text(), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("ratio_from", sa.Numeric()),
        sa.Column("ratio_to", sa.Numeric()),
        sa.Column("amount", sa.Numeric(18, 4)),
        sa.Column("source", sa.Text(), nullable=False),
        sa.UniqueConstraint("isin", "ex_date", "action_type", name="uq_corporate_actions_isin"),
        sa.CheckConstraint(
            "action_type IN ('SPLIT','BONUS','DIVIDEND','RIGHTS','MERGER')",
            name="ck_corporate_actions_action_type_valid",
        ),
    )

    op.create_table(
        "ingest_run",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("job", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.Text(), nullable=False, server_default="RUNNING"),
        sa.Column("rows_written", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", JSONB().with_variant(sa.Text(), "sqlite")),
        sa.CheckConstraint(
            "status IN ('RUNNING','OK','PARTIAL','FAILED')",
            name="ck_ingest_run_status_valid",
        ),
    )

    # TimescaleDB hypertable when the extension is available (the compose stack has it);
    # plain table otherwise so dev/test environments without timescale still work.
    bind = op.get_bind()
    if _timescale_available(bind):
        bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
        bind.execute(
            sa.text(
                "SELECT create_hypertable('ohlcv_daily', 'trade_date', "
                "chunk_time_interval => INTERVAL '1 year', migrate_data => true)"
            )
        )


def downgrade() -> None:
    op.drop_table("ingest_run")
    op.drop_table("corporate_actions")
    op.drop_table("ohlcv_daily")
    op.drop_table("trading_calendar")
    op.drop_table("universe_membership")
    op.drop_table("companies")
    op.drop_table("instruments")
