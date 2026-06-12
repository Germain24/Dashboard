"""daily snapshot + wellbeing score

Revision ID: r212snapshot0
Revises: c3d4e5f6a7b8
Create Date: 2026-06-11 13:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'r212snapshot0'
down_revision: Union[str, None] = 'r201routines0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'daily_snapshot',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('data', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date'),
    )
    op.create_index('ix_daily_snapshot_date', 'daily_snapshot', ['date'])


def downgrade() -> None:
    op.drop_index('ix_daily_snapshot_date', 'daily_snapshot')
    op.drop_table('daily_snapshot')
