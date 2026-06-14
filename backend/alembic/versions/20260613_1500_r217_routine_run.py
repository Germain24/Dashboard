"""journal d'audit des routines (#217)

Revision ID: r217routinerun
Revises: l160booklangue
Create Date: 2026-06-13 15:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "r217routinerun"
down_revision = "l160booklangue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "routine_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("routine_id", sa.Integer(), nullable=False),
        sa.Column("routine_name", sa.String(), nullable=False, server_default=""),
        sa.Column("ran_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="ok"),
        sa.Column("detail", sa.String(), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["routine_id"], ["routine.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_routine_run_routine_id", "routine_run", ["routine_id"])


def downgrade() -> None:
    op.drop_index("ix_routine_run_routine_id", table_name="routine_run")
    op.drop_table("routine_run")
