"""user state: profile, debts, goals, plan_versions

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "profile",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("display_name", sa.Text()),
        sa.Column("monthly_inflow", sa.Numeric(18, 2)),
        sa.Column("fixed_outflow", sa.Numeric(18, 2)),
        sa.Column("variable_outflow", sa.Numeric(18, 2)),
        sa.Column("liquid_balance", sa.Numeric(18, 2)),
        sa.Column("existing_investments", sa.Numeric(18, 2)),
        sa.Column("dependants", sa.Integer(), server_default="0"),
        sa.Column("job_stability", sa.Text()),
        sa.Column("income_variability", sa.Numeric(6, 4)),
        sa.Column("temperament_choice", sa.Text()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("id = 1", name="ck_profile_single_user"),
        sa.CheckConstraint(
            "job_stability IN ('LOW','MEDIUM','HIGH')",
            name="ck_profile_job_stability_valid",
        ),
    )

    op.create_table(
        "debts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("principal_outstanding", sa.Numeric(18, 2), nullable=False),
        sa.Column("annual_rate_pct", sa.Numeric(6, 3), nullable=False),
        sa.Column("min_emi", sa.Numeric(18, 2)),
        sa.Column("tax_deductible", sa.Boolean(), server_default="false"),
    )

    op.create_table(
        "goals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("target_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("priority", sa.Text()),
        sa.CheckConstraint(
            "priority IN ('MUST','SHOULD','WANT')", name="ck_goals_priority_valid"
        ),
    )

    op.create_table(
        "plan_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("profile_snapshot", JSONB().with_variant(sa.Text(), "sqlite"), nullable=False),
        sa.Column("plan_result", JSONB().with_variant(sa.Text(), "sqlite"), nullable=False),
        sa.Column("rationale_md", sa.Text(), nullable=False),
        sa.Column("superseded_by", sa.Uuid()),
    )


def downgrade() -> None:
    op.drop_table("plan_versions")
    op.drop_table("goals")
    op.drop_table("debts")
    op.drop_table("profile")
