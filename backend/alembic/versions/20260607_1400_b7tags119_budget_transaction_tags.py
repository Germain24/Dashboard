"""budget transaction tags (#119)

Revision ID: b7tags119
Revises: d69434536a1c
Create Date: 2026-06-07 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7tags119'
down_revision: Union[str, None] = 'd69434536a1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('budget_transaction', sa.Column('tags', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('budget_transaction', 'tags')
