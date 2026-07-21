"""Livres §5.3: séries/mangas — serie + tome sur book.

Revision ID: l530bookserietome
Revises: v721voyagechecklist
Create Date: 2026-07-20 12:00:00
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "l530bookserietome"
down_revision: str | None = "v721voyagechecklist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # serie="" par défaut : les livres existants restent des ouvrages isolés.
    with op.batch_alter_table("book") as batch_op:
        batch_op.add_column(
            sa.Column("serie", sa.String(), nullable=False, server_default="")
        )
        batch_op.add_column(sa.Column("tome", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("book") as batch_op:
        batch_op.drop_column("tome")
        batch_op.drop_column("serie")
