"""Agenda — RegleRecurrence + Tache + extension Evenement (CONV 5).

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-25 10:00:00

Migration défensive : vérifie l'existence des tables/colonnes avant de les
créer (cf. PLAN.md note 12 — race condition / double-run).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return set(inspector.get_table_names())


def _columns(table: str) -> set[str]:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    existing = _tables()

    # ── Table regle_recurrence ───────────────────────────────────────────
    if "regle_recurrence" not in existing:
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
    if "tache" not in existing:
        op.create_table(
            "tache",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("titre", sa.String, nullable=False),
            sa.Column("deadline", sa.Date, nullable=True),
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
    ev_cols = _columns("evenement")
    with op.batch_alter_table("evenement") as batch_op:
        if "categorie" not in ev_cols:
            batch_op.add_column(sa.Column("categorie", sa.String, nullable=True))
        if "couleur" not in ev_cols:
            batch_op.add_column(sa.Column("couleur", sa.String, nullable=True))
        if "recurrence_id" not in ev_cols:
            # Pas de ForeignKey nommé dans batch_alter_table (SQLite exige un nom
            # explicite sur les contraintes — et de toute façon SQLite n'enforce
            # pas les FK au niveau DDL ; la relation est gérée par SQLModel).
            batch_op.add_column(
                sa.Column("recurrence_id", sa.Integer, nullable=True)
            )


def downgrade() -> None:
    ev_cols = _columns("evenement")
    with op.batch_alter_table("evenement") as batch_op:
        if "recurrence_id" in ev_cols:
            batch_op.drop_column("recurrence_id")
        if "couleur" in ev_cols:
            batch_op.drop_column("couleur")
        if "categorie" in ev_cols:
            batch_op.drop_column("categorie")

    existing = _tables()
    if "tache" in existing:
        try:
            op.drop_index("ix_tache_deadline", "tache")
        except Exception:
            pass
        op.drop_table("tache")
    if "regle_recurrence" in existing:
        op.drop_table("regle_recurrence")
