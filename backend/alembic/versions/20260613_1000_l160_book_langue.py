"""add langue to book (filtre par langue)

Revision ID: l160booklangue
Revises: m6sections001
Create Date: 2026-06-13 10:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "l160booklangue"
down_revision = "m6sections001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("book") as batch_op:
        batch_op.add_column(
            sa.Column("langue", sa.String(), nullable=False, server_default="")
        )


def downgrade() -> None:
    with op.batch_alter_table("book") as batch_op:
        batch_op.drop_column("langue")
