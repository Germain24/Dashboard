"""Voyage optimizer v2: richer wishlist data and live price cache.

Revision ID: v719voyagev2
Revises: f716taxtxdetails
Create Date: 2026-07-19 21:00:00
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v719voyagev2"
down_revision: str | None = "f716taxtxdetails"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("lieu_voyage") as batch_op:
        batch_op.add_column(sa.Column("ordre", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("progression", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("priorite", sa.Integer(), nullable=False, server_default="3"))
        batch_op.add_column(sa.Column("cout_activite", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("cout_transport_local", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("mois_disponibles", sa.String(), nullable=True))

    op.create_table(
        "voyage_price_cache",
        sa.Column("cache_key", sa.String(), nullable=False),
        sa.Column("itineraire", sa.String(), nullable=False),
        sa.Column("dates", sa.String(), nullable=False),
        sa.Column("prix", sa.Float(), nullable=False),
        sa.Column("devise", sa.String(), nullable=False),
        sa.Column("duree_min", sa.Integer(), nullable=False),
        sa.Column("transporteur", sa.String(), nullable=True),
        sa.Column("fetched_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("cache_key"),
    )


def downgrade() -> None:
    op.drop_table("voyage_price_cache")
    with op.batch_alter_table("lieu_voyage") as batch_op:
        batch_op.drop_column("mois_disponibles")
        batch_op.drop_column("cout_transport_local")
        batch_op.drop_column("cout_activite")
        batch_op.drop_column("priorite")
        batch_op.drop_column("progression")
        batch_op.drop_column("ordre")
