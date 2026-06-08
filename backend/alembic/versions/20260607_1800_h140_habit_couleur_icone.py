"""add couleur and icone to habit (#140)

Revision ID: h140couleuricone
Revises: b7tags119
Create Date: 2026-06-07 18:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "h140couleuricone"
down_revision = "b7tags119"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("habit") as batch_op:
        batch_op.add_column(sa.Column("couleur", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("icone", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("habit") as batch_op:
        batch_op.drop_column("icone")
        batch_op.drop_column("couleur")
