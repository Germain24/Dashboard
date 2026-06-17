"""patrimoine_snapshot : suivi du patrimoine net dans le temps (#257)

Revision ID: q257patrimoinesnap
Revises: u226lifegoal
Create Date: 2026-06-17 12:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "q257patrimoinesnap"
down_revision = "u226lifegoal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patrimoine_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("net", sa.Float(), nullable=False, server_default="0"),
        sa.Column("actifs", sa.Float(), nullable=False, server_default="0"),
        sa.Column("passifs", sa.Float(), nullable=False, server_default="0"),
        sa.Column("portefeuille", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_patrimoine_snapshot_date", "patrimoine_snapshot", ["date"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_patrimoine_snapshot_date", table_name="patrimoine_snapshot")
    op.drop_table("patrimoine_snapshot")
