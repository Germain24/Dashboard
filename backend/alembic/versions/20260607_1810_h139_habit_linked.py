"""add linked_ids to habit (#139)

Revision ID: h139linkedids
Revises: h140couleuricone
Create Date: 2026-06-07 18:10:00
"""

from alembic import op
import sqlalchemy as sa

revision = "h139linkedids"
down_revision = "h140couleuricone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("habit") as batch_op:
        batch_op.add_column(sa.Column("linked_ids", sa.String(), nullable=True, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("habit") as batch_op:
        batch_op.drop_column("linked_ids")
