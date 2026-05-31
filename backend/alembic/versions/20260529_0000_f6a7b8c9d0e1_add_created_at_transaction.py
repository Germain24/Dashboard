"""Add created_at to transaction table.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-29 00:00:00
"""
from __future__ import annotations
import datetime
import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ajouter created_at a transaction (manquant dans la migration initiale)
    with op.batch_alter_table("transaction") as batch:
        batch.add_column(
            sa.Column(
                "created_at",
                sa.DateTime,
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("transaction") as batch:
        batch.drop_column("created_at")
