"""add page_courante to book (#144)

Revision ID: m144pagecourante
Revises: h139linkedids
Create Date: 2026-06-08 11:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "m144pagecourante"
down_revision = "h139linkedids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("book") as batch_op:
        batch_op.add_column(sa.Column("page_courante", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("book") as batch_op:
        batch_op.drop_column("page_courante")
