"""qual_facts (LLM extraction output) + cascade_gap (the failure log)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "qual_facts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("isin", sa.Text(), nullable=False),
        sa.Column(
            "filing_id",
            sa.BigInteger(),
            sa.ForeignKey("filings.id", name="fk_qual_facts_filing_id"),
        ),
        sa.Column("fact_type", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text()),
        sa.Column("magnitude_band", sa.Text()),
        sa.Column("horizon_relevance", JSONB().with_variant(sa.Text(), "sqlite")),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("evidence_span", sa.Text()),
        sa.Column("extracted_by", sa.Text(), nullable=False),
        sa.Column(
            "extracted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "direction IN ('POSITIVE','NEGATIVE','NEUTRAL')",
            name="ck_qual_facts_direction_valid",
        ),
    )

    op.create_table(
        "cascade_gap",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("isin", sa.Text()),
        sa.Column("horizon", sa.Text()),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("raw_output", sa.Text()),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("cascade_gap")
    op.drop_table("qual_facts")
