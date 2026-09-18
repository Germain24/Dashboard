"""credit_profile / credit_account / credit_score_entry : marge de crédit (#marge-credit)

Revision ID: r705creditmargin
Revises: 763cb2d89706
Create Date: 2026-07-05 00:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "r705creditmargin"
down_revision = "763cb2d89706"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("revenu_annuel", sa.Float(), nullable=False, server_default="0"),
        sa.Column("date_arrivee_canada", sa.Date(), nullable=False),
        sa.Column("date_cible", sa.Date(), nullable=False),
        sa.Column("nom", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "credit_account",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("institution", sa.String(), nullable=False),
        sa.Column("produit", sa.String(), nullable=False),
        sa.Column("limite_actuelle", sa.Float(), nullable=False, server_default="0"),
        sa.Column("date_ouverture", sa.Date(), nullable=False),
        sa.Column("derniere_augmentation", sa.Date(), nullable=True),
        sa.Column("statut", sa.String(), nullable=False, server_default="actif"),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "credit_score_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_score_entry_date", "credit_score_entry", ["date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_credit_score_entry_date", table_name="credit_score_entry")
    op.drop_table("credit_score_entry")
    op.drop_table("credit_account")
    op.drop_table("credit_profile")
