"""Store gross dividends and foreign withholding tax.

Revision ID: f716taxtxdetails
Revises: f715buffettrun
Create Date: 2026-07-16 10:00:00
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f716taxtxdetails"
down_revision: str | None = "f715buffettrun"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("transaction") as batch_op:
        batch_op.add_column(sa.Column("montant_brut", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "retenue_source",
                sa.Float(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("transaction") as batch_op:
        batch_op.drop_column("retenue_source")
        batch_op.drop_column("montant_brut")
