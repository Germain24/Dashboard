"""drop duffel_price_cache table

Duffel API dependency removed -- flight pricing is now estimated locally
(distance-based formula + PrixVolsEstimes.xlsx overrides), no more per-pair
cached API responses to store.

Revision ID: 9e3b27b9bf48
Revises: s706creditrules
Create Date: 2026-07-10 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '9e3b27b9bf48'
down_revision: Union[str, None] = 's706creditrules'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('duffel_price_cache')


def downgrade() -> None:
    op.create_table('duffel_price_cache',
    sa.Column('cache_key', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('origine_iata', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('destination_iata', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('date_reference', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('prix', sa.Float(), nullable=False),
    sa.Column('devise', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('duree_min', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('cache_key')
    )
