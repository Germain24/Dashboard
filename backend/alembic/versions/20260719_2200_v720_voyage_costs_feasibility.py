"""Voyage v2.1: split daily costs and activity feasibility.

Revision ID: v720voyagecosts
Revises: v719voyagev2
Create Date: 2026-07-19 22:00:00
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v720voyagecosts"
down_revision: str | None = "v719voyagev2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("lieu_voyage") as batch_op:
        batch_op.add_column(sa.Column("cout_hebergement_jour", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("cout_nourriture_jour", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("statut", sa.String(), nullable=False, server_default="possible")
        )
        batch_op.add_column(sa.Column("raison_indisponible", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("lieu_voyage") as batch_op:
        batch_op.drop_column("raison_indisponible")
        batch_op.drop_column("statut")
        batch_op.drop_column("cout_nourriture_jour")
        batch_op.drop_column("cout_hebergement_jour")
