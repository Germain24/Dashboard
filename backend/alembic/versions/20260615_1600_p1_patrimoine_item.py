"""patrimoine_item : actifs manuels & passifs (RealT, emprunt)

Revision ID: p1patrimoine
Revises: a216runrollback
Create Date: 2026-06-15 16:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "p1patrimoine"
down_revision = "a216runrollback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patrimoine_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(), nullable=False, server_default="actif"),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("categorie", sa.String(), nullable=False, server_default=""),
        sa.Column("valeur", sa.Float(), nullable=False, server_default="0"),
        sa.Column("taux_pct", sa.Float(), nullable=True),
        sa.Column("mensualite", sa.Float(), nullable=True),
        sa.Column("devise", sa.String(), nullable=False, server_default="EUR"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("patrimoine_item")
