"""etudes: drop stub etude, create cours/evaluation/session_etude.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-26 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Supprimer le stub CONV 1 (aucune donnée réelle dedans)
    op.drop_table("etude")

    # ------------------------------------------------------------------ cours
    op.create_table(
        "cours",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("nom", sa.String(), nullable=False),
        sa.Column("semestre", sa.String(), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("prof", sa.String(), nullable=True),
        sa.Column("local", sa.String(), nullable=True),
        sa.Column("note_finale", sa.Float(), nullable=True),
        sa.Column("actif", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cours_code", "cours", ["code"])
    op.create_index("ix_cours_semestre", "cours", ["semestre"])

    # ------------------------------------------------------------ evaluation
    op.create_table(
        "evaluation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cours_id", sa.Integer(), nullable=False),
        sa.Column("titre", sa.String(), nullable=False),
        sa.Column("type_eval", sa.String(), nullable=False, server_default="autre"),
        sa.Column("date_limite", sa.Date(), nullable=True),
        sa.Column("note_obtenue", sa.Float(), nullable=True),
        sa.Column("note_max", sa.Float(), nullable=True, server_default="100"),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["cours_id"], ["cours.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_cours_id", "evaluation", ["cours_id"])
    op.create_index("ix_evaluation_date_limite", "evaluation", ["date_limite"])

    # --------------------------------------------------------- session_etude
    op.create_table(
        "session_etude",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cours_id", sa.Integer(), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("duree_min", sa.Integer(), nullable=False),
        sa.Column("sujet", sa.String(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["cours_id"], ["cours.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_session_etude_cours_id", "session_etude", ["cours_id"])
    op.create_index("ix_session_etude_date", "session_etude", ["date"])


def downgrade() -> None:
    op.drop_table("session_etude")
    op.drop_table("evaluation")
    op.drop_table("cours")

    op.create_table(
        "etude",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("matiere", sa.String(), nullable=False),
        sa.Column("sujet", sa.String(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("duree_min", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
