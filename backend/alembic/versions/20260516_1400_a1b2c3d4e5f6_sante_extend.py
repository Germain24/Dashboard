"""sante: extend MesureSante + PlanNutrition + add NutritionGoal

CONV 3 — Module Santé / Nutrition

Changements :
- mesure_sante : ajout `photo_url`, `note`
- plan_nutrition : ajout `poids_used`, `intensite`, `base_targets`, `totals`,
  `consumed`, `warning` ; renforce l'unicité de `date`
- nutrition_goal : nouvelle table (singleton actif)

Revision ID: a1b2c3d4e5f6
Revises: cd9aba577b3c
Create Date: 2026-05-16 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "cd9aba577b3c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── mesure_sante : photo_url + note ──
    with op.batch_alter_table("mesure_sante", schema=None) as batch_op:
        batch_op.add_column(sa.Column("photo_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column("note", sqlmodel.sql.sqltypes.AutoString(), nullable=True))

    # ── plan_nutrition : nouveaux champs + unicité date ──
    with op.batch_alter_table("plan_nutrition", schema=None) as batch_op:
        batch_op.add_column(sa.Column("poids_used", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("intensite", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column("base_targets", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("totals", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("consumed", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("warning", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        # On retire l'index non-unique pour le remplacer par un index unique
        batch_op.drop_index("ix_plan_nutrition_date")
        batch_op.create_index("ix_plan_nutrition_date", ["date"], unique=True)

    # ── nutrition_goal : nouvelle table ──
    op.create_table(
        "nutrition_goal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date_set", sa.Date(), nullable=False),
        sa.Column("poids_cible", sa.Float(), nullable=True),
        sa.Column("body_fat_target_pct", sa.Float(), nullable=True),
        sa.Column("date_cible", sa.Date(), nullable=True),
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("surplus_kcal_sport", sa.Float(), nullable=False),
        sa.Column("rest_factor", sa.Float(), nullable=False),
        sa.Column("sport_days", sa.JSON(), nullable=True),
        sa.Column("actif", sa.Boolean(), nullable=False),
        sa.Column("note", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("nutrition_goal", schema=None) as batch_op:
        batch_op.create_index("ix_nutrition_goal_actif", ["actif"], unique=False)
        batch_op.create_index("ix_nutrition_goal_date_set", ["date_set"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("nutrition_goal", schema=None) as batch_op:
        batch_op.drop_index("ix_nutrition_goal_date_set")
        batch_op.drop_index("ix_nutrition_goal_actif")
    op.drop_table("nutrition_goal")

    with op.batch_alter_table("plan_nutrition", schema=None) as batch_op:
        batch_op.drop_index("ix_plan_nutrition_date")
        batch_op.create_index("ix_plan_nutrition_date", ["date"], unique=False)
        batch_op.drop_column("warning")
        batch_op.drop_column("consumed")
        batch_op.drop_column("totals")
        batch_op.drop_column("base_targets")
        batch_op.drop_column("intensite")
        batch_op.drop_column("poids_used")

    with op.batch_alter_table("mesure_sante", schema=None) as batch_op:
        batch_op.drop_column("note")
        batch_op.drop_column("photo_url")
