"""films_series watchlist

Revision ID: f3a4b5c6d7e8
Revises: d2f280517703
Create Date: 2026-06-11 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, None] = 'd2f280517703'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'watch_item',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('titre', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('tmdb_id', sa.Integer(), nullable=True),
        sa.Column('statut', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('note', sa.Float(), nullable=True),
        sa.Column('annee', sa.Integer(), nullable=True),
        sa.Column('genres', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('poster_url', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('duree_min', sa.Integer(), nullable=True),
        sa.Column('nb_saisons', sa.Integer(), nullable=True),
        sa.Column('nb_episodes_total', sa.Integer(), nullable=True),
        sa.Column('synopsis', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('date_vue', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'serie_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('watch_item_id', sa.Integer(), nullable=False),
        sa.Column('saison', sa.Integer(), nullable=False),
        sa.Column('episode_courant', sa.Integer(), nullable=False),
        sa.Column('episodes_saison', sa.Integer(), nullable=True),
        sa.Column('date_derniere_vue', sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(['watch_item_id'], ['watch_item.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('serie_progress', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_serie_progress_watch_item_id'), ['watch_item_id'], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table('serie_progress', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_serie_progress_watch_item_id'))
    op.drop_table('serie_progress')
    op.drop_table('watch_item')
