"""alerts table + sim_positions flag columns (docs/05 breach flow)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("kind", sa.Text(), nullable=False),
        # unique: one breach alert per falsifier, ever — re-running the
        # nightly check is idempotent by construction
        sa.Column(
            "falsifier_id",
            sa.Uuid(),
            sa.ForeignKey("falsifiers.id", name="fk_alerts_falsifier_id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "recommendation_id",
            sa.Uuid(),
            sa.ForeignKey("recommendations.id", name="fk_alerts_recommendation_id"),
            nullable=False,
        ),
        sa.Column("isin", sa.Text(), nullable=False),
        sa.Column("tradingsymbol", sa.Text()),
        sa.Column("horizon", sa.Text(), nullable=False),
        sa.Column("field_id", sa.Text(), nullable=False),
        sa.Column("operator", sa.Text(), nullable=False),
        sa.Column("threshold", sa.Numeric(20, 6), nullable=False),
        sa.Column("observed_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("observed_as_of", sa.Date(), nullable=False),
        sa.Column("thesis_line", sa.Text(), nullable=False),
        sa.Column(
            "thesis_line_found",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "raised_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
    )

    op.add_column("sim_positions", sa.Column("flagged_at", sa.DateTime(timezone=True)))
    op.add_column("sim_positions", sa.Column("flag_reason", sa.Text()))


def downgrade() -> None:
    op.drop_column("sim_positions", "flag_reason")
    op.drop_column("sim_positions", "flagged_at")
    op.drop_table("alerts")
