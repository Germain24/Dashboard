"""Finance module: rename watchlist_entry -> buffett_run_result, add buffett_run.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-27 10:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Créer buffett_run AVANT d'y référencer via FK
    op.create_table(
        "buffett_run",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_date", sa.Date, nullable=False, index=True),
        sa.Column(
            "statut",
            sa.String,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("n_tickers_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("n_tickers_analyzed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("progress_pct", sa.Float, nullable=False, server_default="0"),
        sa.Column("params_json", sa.JSON, nullable=True),
        sa.Column("duree_sec", sa.Float, nullable=True),
        sa.Column("resume", sa.Text, nullable=True),
        sa.Column("erreur", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # 2. Renommer watchlist_entry → buffett_run_result
    op.rename_table("watchlist_entry", "buffett_run_result")

    # 3. Ajouter colonnes supplémentaires à buffett_run_result
    with op.batch_alter_table("buffett_run_result") as batch:
        batch.add_column(
            sa.Column("run_id", sa.Integer, nullable=True)
        )
        batch.add_column(
            sa.Column("allocation_pct", sa.Float, nullable=True)
        )
        batch.add_column(
            sa.Column("broker_cible", sa.String, nullable=True)
        )
        batch.create_foreign_key(
            "fk_brr_run_id",
            "buffett_run",
            ["run_id"],
            ["id"],
        )

    # 4. Snapshot quotidien : ajouter colonnes manquantes si nécessaire
    # (snapshot_portefeuille existait déjà — pas de modif)


def downgrade() -> None:
    with op.batch_alter_table("buffett_run_result") as batch:
        batch.drop_constraint("fk_brr_run_id", type_="foreignkey")
        batch.drop_column("broker_cible")
        batch.drop_column("allocation_pct")
        batch.drop_column("run_id")

    op.rename_table("buffett_run_result", "watchlist_entry")
    op.drop_table("buffett_run")
