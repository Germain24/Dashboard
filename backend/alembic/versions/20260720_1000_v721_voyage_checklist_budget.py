"""Voyage §5.4: voyage confirmé + checklist + budget par étape.

Revision ID: v721voyagechecklist
Revises: v720voyagecosts
Create Date: 2026-07-20 10:00:00
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v721voyagechecklist"
down_revision: str | None = "v720voyagecosts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "voyage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("titre", sa.String(), nullable=False),
        sa.Column("date_debut", sa.Date(), nullable=False),
        sa.Column("date_fin", sa.Date(), nullable=False),
        sa.Column("depart_iata", sa.String(), nullable=True),
        sa.Column("arrivee_iata", sa.String(), nullable=True),
        sa.Column("cree_le", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Pas de FK sur lieu_id : sync_voyage vide et réécrit lieu_voyage à chaque
    # import Excel, les ids ne survivent pas à une resynchro (nom/pays dénormalisés).
    op.create_table(
        "voyage_etape",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("voyage_id", sa.Integer(), nullable=False),
        sa.Column("lieu_id", sa.Integer(), nullable=True),
        sa.Column("nom", sa.String(), nullable=False),
        sa.Column("ville", sa.String(), nullable=True),
        sa.Column("pays", sa.String(), nullable=True),
        sa.Column("ordre", sa.Integer(), nullable=False),
        sa.Column("jours", sa.Integer(), nullable=False),
        sa.Column("date_arrivee", sa.Date(), nullable=True),
        sa.Column("date_depart", sa.Date(), nullable=True),
        sa.Column("cout_estime", sa.Float(), nullable=False),
        sa.Column("cout_reel", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["voyage_id"], ["voyage.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_voyage_etape_voyage_id", "voyage_etape", ["voyage_id"])
    op.create_table(
        "voyage_checklist_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("voyage_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("fait", sa.Boolean(), nullable=False),
        sa.Column("ordre", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["voyage_id"], ["voyage.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_voyage_checklist_item_voyage_id", "voyage_checklist_item", ["voyage_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_voyage_checklist_item_voyage_id", table_name="voyage_checklist_item")
    op.drop_table("voyage_checklist_item")
    op.drop_index("ix_voyage_etape_voyage_id", table_name="voyage_etape")
    op.drop_table("voyage_etape")
    op.drop_table("voyage")
