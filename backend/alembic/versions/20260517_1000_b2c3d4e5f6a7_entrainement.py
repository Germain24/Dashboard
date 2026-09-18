"""entrainement: add exercice, programme, programme_jour, set_serie,
course_cardio + extend seance

CONV 7 — Module Entraînement (sport, prise de muscle).

Changements :
- exercice (nouvelle table) : catalogue d'exercices
- programme (nouvelle table) : programme hebdomadaire (singleton actif)
- programme_jour (nouvelle table) : 7 jours par programme
- set_serie (nouvelle table) : séries loggées (reps × poids × RPE)
- course_cardio (nouvelle table) : courses à pied (distance + temps)
- seance (existante) : + programme_jour_id, intensite, source

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-17 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── exercice ──
    op.create_table(
        "exercice",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nom", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("categorie", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("muscles", sa.JSON(), nullable=True),
        sa.Column("type_mouvement", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("unilateral", sa.Boolean(), nullable=False),
        sa.Column("source", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("note", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("exercice", schema=None) as batch_op:
        batch_op.create_index("ix_exercice_nom", ["nom"], unique=True)
        batch_op.create_index("ix_exercice_categorie", ["categorie"], unique=False)

    # ── programme ──
    op.create_table(
        "programme",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nom", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("actif", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("programme", schema=None) as batch_op:
        batch_op.create_index("ix_programme_actif", ["actif"], unique=False)

    # ── programme_jour ──
    op.create_table(
        "programme_jour",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("programme_id", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("label", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("slots", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["programme_id"], ["programme.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("programme_jour", schema=None) as batch_op:
        batch_op.create_index("ix_programme_jour_programme_id", ["programme_id"], unique=False)
        batch_op.create_index("ix_programme_jour_weekday", ["weekday"], unique=False)

    # ── seance : extensions ──
    with op.batch_alter_table("seance", schema=None) as batch_op:
        batch_op.add_column(sa.Column("programme_jour_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("intensite", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column("source", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="manual"))
        batch_op.create_foreign_key(
            "fk_seance_programme_jour",
            "programme_jour",
            ["programme_jour_id"],
            ["id"],
        )

    # ── set_serie ──
    op.create_table(
        "set_serie",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seance_id", sa.Integer(), nullable=False),
        sa.Column("exercice_id", sa.Integer(), nullable=False),
        sa.Column("ordre", sa.Integer(), nullable=False),
        sa.Column("reps", sa.Integer(), nullable=False),
        sa.Column("poids_kg", sa.Float(), nullable=False),
        sa.Column("rpe", sa.Float(), nullable=True),
        sa.Column("echec", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["seance_id"], ["seance.id"]),
        sa.ForeignKeyConstraint(["exercice_id"], ["exercice.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("set_serie", schema=None) as batch_op:
        batch_op.create_index("ix_set_serie_seance_id", ["seance_id"], unique=False)
        batch_op.create_index("ix_set_serie_exercice_id", ["exercice_id"], unique=False)

    # ── course_cardio ──
    op.create_table(
        "course_cardio",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False),
        sa.Column("duree_sec", sa.Integer(), nullable=False),
        sa.Column("note", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("source", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("course_cardio", schema=None) as batch_op:
        batch_op.create_index("ix_course_cardio_date", ["date"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("course_cardio", schema=None) as batch_op:
        batch_op.drop_index("ix_course_cardio_date")
    op.drop_table("course_cardio")

    with op.batch_alter_table("set_serie", schema=None) as batch_op:
        batch_op.drop_index("ix_set_serie_exercice_id")
        batch_op.drop_index("ix_set_serie_seance_id")
    op.drop_table("set_serie")

    with op.batch_alter_table("seance", schema=None) as batch_op:
        batch_op.drop_constraint("fk_seance_programme_jour", type_="foreignkey")
        batch_op.drop_column("source")
        batch_op.drop_column("intensite")
        batch_op.drop_column("programme_jour_id")

    with op.batch_alter_table("programme_jour", schema=None) as batch_op:
        batch_op.drop_index("ix_programme_jour_weekday")
        batch_op.drop_index("ix_programme_jour_programme_id")
    op.drop_table("programme_jour")

    with op.batch_alter_table("programme", schema=None) as batch_op:
        batch_op.drop_index("ix_programme_actif")
    op.drop_table("programme")

    with op.batch_alter_table("exercice", schema=None) as batch_op:
        batch_op.drop_index("ix_exercice_categorie")
        batch_op.drop_index("ix_exercice_nom")
    op.drop_table("exercice")
