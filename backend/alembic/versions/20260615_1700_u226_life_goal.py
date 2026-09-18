"""life_goal : objectifs de vie inter-modules (#226)

Revision ID: u226lifegoal
Revises: p1patrimoine
Create Date: 2026-06-15 17:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "u226lifegoal"
down_revision = "p1patrimoine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "life_goal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("titre", sa.String(), nullable=False),
        sa.Column("echeance", sa.Date(), nullable=True),
        sa.Column("objectifs", sa.String(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("life_goal")
