"""Scope Buffett result uniqueness to one ticker per run.

Revision ID: f715buffettrun
Revises: 9e3b27b9bf48
Create Date: 2026-07-15 12:00:00
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f715buffettrun"
down_revision: str | None = "9e3b27b9bf48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("buffett_run_result") as batch_op:
        batch_op.drop_index("ix_buffett_run_result_ticker")
        batch_op.create_index(
            "ix_buffett_run_result_ticker", ["ticker"], unique=False
        )
        batch_op.create_unique_constraint(
            "uq_buffett_run_result_run_ticker", ["run_id", "ticker"]
        )


def downgrade() -> None:
    duplicate = op.get_bind().execute(
        sa.text(
            "SELECT ticker FROM buffett_run_result "
            "GROUP BY ticker HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "Downgrade impossible sans perte: plusieurs runs contiennent le ticker "
            f"{duplicate[0]!r}."
        )

    with op.batch_alter_table("buffett_run_result") as batch_op:
        batch_op.drop_constraint(
            "uq_buffett_run_result_run_ticker", type_="unique"
        )
        batch_op.drop_index("ix_buffett_run_result_ticker")
        batch_op.create_index(
            "ix_buffett_run_result_ticker", ["ticker"], unique=True
        )
