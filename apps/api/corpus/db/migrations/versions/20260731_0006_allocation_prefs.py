"""profile columns for allocation preferences (docs/04 gate inputs)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # LOW is the conservative default: HIGH-knowledge vehicles stay gated
    # until the user claims otherwise. max_lock_in_months NULL means "no
    # constraint stated" — never zero-filled.
    op.add_column(
        "profile",
        sa.Column("self_rated_knowledge", sa.Text(), server_default="LOW"),
    )
    op.add_column("profile", sa.Column("max_lock_in_months", sa.Integer()))
    with op.batch_alter_table("profile") as batch:
        batch.create_check_constraint(
            "self_rated_knowledge_valid",
            "self_rated_knowledge IN ('LOW','MEDIUM','HIGH')",
        )


def downgrade() -> None:
    with op.batch_alter_table("profile") as batch:
        batch.drop_constraint("self_rated_knowledge_valid", type_="check")
    op.drop_column("profile", "max_lock_in_months")
    op.drop_column("profile", "self_rated_knowledge")
