"""recommendations, falsifiers, sim positions/marks, calibration results

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JsonCol = JSONB().with_variant(sa.Text(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("isin", sa.Text(), nullable=False),
        sa.Column("tradingsymbol", sa.Text()),
        sa.Column("instrument_token", sa.BigInteger()),
        sa.Column("horizon", sa.Text(), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_on", sa.Date(), nullable=False),
        sa.Column("ref_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("band_bear_pct", sa.Numeric(8, 3), nullable=False),
        sa.Column("band_base_pct", sa.Numeric(8, 3), nullable=False),
        sa.Column("band_bull_pct", sa.Numeric(8, 3), nullable=False),
        sa.Column("conviction", sa.Text(), nullable=False),
        sa.Column("suggested_size_inr", sa.Numeric(18, 2), nullable=False),
        sa.Column("score_snapshot", JsonCol, nullable=False),
        sa.Column("weights_version", sa.Text(), nullable=False),
        sa.Column("report_md", sa.Text(), nullable=False),
        sa.Column("net_of_costs_hurdle_pct", sa.Numeric(8, 3), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="LIVE"),
        sa.CheckConstraint(
            "horizon IN ('SHORT','MID','LONG')", name="ck_recommendations_horizon_valid"
        ),
        sa.CheckConstraint(
            "conviction IN ('LOW','MODERATE','HIGH')",
            name="ck_recommendations_conviction_valid",
        ),
        sa.CheckConstraint(
            "status IN ('LIVE','EXPIRED','INVALIDATED')",
            name="ck_recommendations_rec_status_valid",
        ),
        sa.CheckConstraint(
            "band_bear_pct < band_base_pct AND band_base_pct < band_bull_pct",
            name="ck_recommendations_band_ordered",
        ),
    )

    op.create_table(
        "falsifiers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "recommendation_id",
            sa.Uuid(),
            sa.ForeignKey(
                "recommendations.id", name="fk_falsifiers_recommendation_id"
            ),
            nullable=False,
        ),
        sa.Column("field_id", sa.Text(), nullable=False),
        sa.Column("operator", sa.Text(), nullable=False),
        sa.Column("threshold", sa.Numeric(20, 6), nullable=False),
        sa.Column("human_text", sa.Text(), nullable=False),
        sa.Column("breached_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "operator IN ('LT','LTE','GT','GTE','CROSSES_BELOW','CROSSES_ABOVE')",
            name="ck_falsifiers_operator_valid",
        ),
    )

    op.create_table(
        "sim_positions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "recommendation_id",
            sa.Uuid(),
            sa.ForeignKey(
                "recommendations.id", name="fk_sim_positions_recommendation_id"
            ),
            nullable=False,
        ),
        sa.Column("isin", sa.Text(), nullable=False),
        sa.Column("instrument_token", sa.BigInteger()),
        sa.Column("opened_on", sa.Date(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("entry_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("entry_costs_inr", sa.Numeric(18, 2), nullable=False),
        sa.Column("thesis_snapshot_md", sa.Text(), nullable=False),
        sa.Column("closed_on", sa.Date()),
        sa.Column("exit_price", sa.Numeric(18, 4)),
        sa.Column("exit_costs_inr", sa.Numeric(18, 2)),
        sa.Column("close_reason", sa.Text()),
        sa.Column("journal_note", sa.Text()),
        sa.CheckConstraint(
            "close_reason IN ('MANUAL','FALSIFIER','EXPIRY','THESIS_CHANGED')",
            name="ck_sim_positions_close_reason_valid",
        ),
    )

    op.create_table(
        "sim_marks",
        sa.Column(
            "position_id",
            sa.Uuid(),
            sa.ForeignKey("sim_positions.id", name="fk_sim_marks_position_id"),
            primary_key=True,
        ),
        sa.Column("trade_date", sa.Date(), primary_key=True),
        sa.Column("close_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("mtm_inr", sa.Numeric(18, 2), nullable=False),
        sa.Column("unrealised_pct", sa.Numeric(10, 4), nullable=False),
        sa.Column("drawdown_from_peak_pct", sa.Numeric(10, 4), nullable=False),
    )

    op.create_table(
        "calibration_results",
        sa.Column(
            "recommendation_id",
            sa.Uuid(),
            sa.ForeignKey(
                "recommendations.id", name="fk_calibration_results_recommendation_id"
            ),
            primary_key=True,
        ),
        sa.Column("scored_on", sa.Date(), nullable=False),
        sa.Column("actual_return_pct", sa.Numeric(10, 4), nullable=False),
        sa.Column("actual_net_return_pct", sa.Numeric(10, 4), nullable=False),
        sa.Column("index_return_pct", sa.Numeric(10, 4)),
        sa.Column("in_band", sa.Boolean(), nullable=False),
        sa.Column("direction_correct", sa.Boolean(), nullable=False),
        sa.Column("brier", sa.Numeric(8, 5)),
        sa.Column("band_error_pct", sa.Numeric(10, 4)),
        sa.Column("calibration_version", sa.Text(), nullable=False),
    )

    # The immutability trigger: recommendations accept UPDATE only on status.
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION reject_recommendation_update()
            RETURNS trigger AS $$
            BEGIN
                IF to_jsonb(NEW) - 'status' IS DISTINCT FROM to_jsonb(OLD) - 'status' THEN
                    RAISE EXCEPTION
                        'recommendations are immutable; only status may change';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            """
            CREATE TRIGGER recommendations_immutable
            BEFORE UPDATE ON recommendations
            FOR EACH ROW EXECUTE FUNCTION reject_recommendation_update()
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS recommendations_immutable ON recommendations")
        op.execute("DROP FUNCTION IF EXISTS reject_recommendation_update")
    op.drop_table("calibration_results")
    op.drop_table("sim_marks")
    op.drop_table("sim_positions")
    op.drop_table("falsifiers")
    op.drop_table("recommendations")
