"""fundamentals, filings, shareholding, metric_values, metric_gaps

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fundamentals_period",
        sa.Column("isin", sa.Text(), primary_key=True),
        sa.Column("period_end", sa.Date(), primary_key=True),
        sa.Column("period_type", sa.Text(), primary_key=True),
        sa.Column("consolidated", sa.Boolean(), primary_key=True),
        sa.Column("line_item", sa.Text(), primary_key=True),
        sa.Column("value", sa.Numeric(20, 4)),
        sa.Column("unit", sa.Text(), nullable=False, server_default="INR_CR"),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "period_type IN ('Q','H','FY')",
            name="ck_fundamentals_period_period_type_valid",
        ),
    )

    op.create_table(
        "filings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("isin", sa.Text(), nullable=False),
        sa.Column("filed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("headline", sa.Text()),
        sa.Column("body", sa.Text()),
        sa.Column("url", sa.Text()),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("content_hash", name="uq_filings_content_hash"),
        sa.CheckConstraint(
            "category IN ('RESULTS','ANNOUNCEMENT','PLEDGE','SHP','CONCALL','AR')",
            name="ck_filings_category_valid",
        ),
    )

    op.create_table(
        "shareholding",
        sa.Column("isin", sa.Text(), primary_key=True),
        sa.Column("period_end", sa.Date(), primary_key=True),
        sa.Column("promoter_pct", sa.Numeric(6, 3)),
        sa.Column("promoter_pledged_pct", sa.Numeric(6, 3)),
        sa.Column("fii_pct", sa.Numeric(6, 3)),
        sa.Column("dii_pct", sa.Numeric(6, 3)),
        sa.Column("public_pct", sa.Numeric(6, 3)),
        sa.Column("source", sa.Text(), nullable=False),
    )

    op.create_table(
        "metric_values",
        sa.Column("isin", sa.Text(), primary_key=True),
        sa.Column("field_id", sa.Text(), primary_key=True),
        sa.Column("as_of", sa.Date(), primary_key=True),
        sa.Column("value", sa.Numeric(20, 6)),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("inputs_hash", sa.Text(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "metric_gaps",
        sa.Column("isin", sa.Text(), primary_key=True),
        sa.Column("field_id", sa.Text(), primary_key=True),
        sa.Column("as_of", sa.Date(), primary_key=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "reason IN ('INSUFFICIENT_HISTORY','SOURCE_STALE','NOT_APPLICABLE')",
            name="ck_metric_gaps_reason_valid",
        ),
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        available = bind.execute(
            sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb'")
        ).scalar()
        if available:
            bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
            bind.execute(
                sa.text(
                    "SELECT create_hypertable('metric_values', 'as_of', "
                    "chunk_time_interval => INTERVAL '1 year', migrate_data => true)"
                )
            )


def downgrade() -> None:
    op.drop_table("metric_gaps")
    op.drop_table("metric_values")
    op.drop_table("shareholding")
    op.drop_table("filings")
    op.drop_table("fundamentals_period")
