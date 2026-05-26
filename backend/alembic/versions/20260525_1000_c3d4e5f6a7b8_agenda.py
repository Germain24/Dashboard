"""Agenda — RegleRecurrence + Tache + extension Evenement (CONV 5).

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-25 10:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Table regle_recurrence ───────────────────────────────────────────
    op.create_table(
        "regle_recurrence",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("titre", sa.String, nullable=False),
        sa.Column("weekdays", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("start_time", sa.String, nullable=False),
        sa.Column("end_time", sa.String, nullable=False),
        sa.Column("lieu", sa.String, nullable=True),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("categorie", sa.String, nullable=True),
        sa.Column("couleur", sa.String, nullable=True),
        sa.Column("until", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )

    # ── Table tache ──────────────────────────────────────────────────────
    op.create_table(
        "tache",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("titre", sa.String, nullable=False),
        sa.Column("deadline", sa.Date, nullable=True, index=True),
        sa.Column("priorite", sa.Integer, nullable=False, server_default="3"),
        sa.Column("statut", sa.String, nullable=False, server_default="todo"),
        sa.Column("duree_estimee_min", sa.Integer, nullable=True),
        sa.Column("note", sa.String, nullable=True),
        sa.Column("categorie", sa.String, nullable=True),
        sa.Column("source", sa.String, nullable=True),
        sa.Column("source_id", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_tache_deadline", "tache", ["deadline"])

    # ── Extension de la table evenement ──────────────────────────────────
    with op.batch_alter_table("evenement") as batch_op:
        batch_op.add_column(sa.Column("categorie", sa.String, nullable=True))
        batch_op.add_column(sa.Column("couleur", sa.String, nullable=True))
        batch_op.add_column(
            sa.Column(
                "recurrence_id",
                sa.Integer,
                sa.ForeignKey("regle_recurrence.id"),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("evenement") as batch_op:
        batch_op.drop_column("recurrence_id")
        batch_op.drop_column("couleur")
        batch_op.drop_column("categorie")

    op.drop_index("ix_tache_deadline", "tache")
    op.drop_table("tache")
    op.drop_table("regle_recurrence")
