"""modules travail, objectifs, gaming, langues

Revision ID: m6sections001
Revises: r212snapshot0
Create Date: 2026-06-12 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'm6sections001'
down_revision: Union[str, None] = 'r212snapshot0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Correctif : le modèle DailySnapshot déclare date unique, mais la migration
    # r212snapshot0 a créé l'index sans unique=True.
    op.drop_index('ix_daily_snapshot_date', 'daily_snapshot')
    op.create_index('ix_daily_snapshot_date', 'daily_snapshot', ['date'], unique=True)
    op.create_table(
        'work_shift',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date_jour', sa.Date(), nullable=False),
        sa.Column('heure_debut', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('heure_fin', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('pause_min', sa.Integer(), nullable=False),
        sa.Column('taux_horaire', sa.Float(), nullable=True),
        sa.Column('role', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('statut', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('note', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'long_term_goal',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('titre', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('categorie', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('statut', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('echeance', sa.Date(), nullable=True),
        sa.Column('progression', sa.Integer(), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('lien', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('cree_le', sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'game',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('titre', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('plateforme', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('statut', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('note', sa.Integer(), nullable=True),
        sa.Column('heures', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'game_goal',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('titre', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('contenu', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('fait', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['game_id'], ['game.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'vocab_entry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('terme', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('lecture', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('traduction', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('tags', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('maitrise', sa.Integer(), nullable=False),
        sa.Column('cree_le', sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'projet_international',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('titre', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('statut', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('echeance', sa.Date(), nullable=True),
        sa.Column('budget_estime', sa.Float(), nullable=True),
        sa.Column('notes', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_index('ix_daily_snapshot_date', 'daily_snapshot')
    op.create_index('ix_daily_snapshot_date', 'daily_snapshot', ['date'])
    op.drop_table('projet_international')
    op.drop_table('vocab_entry')
    op.drop_table('game_goal')
    op.drop_table('game')
    op.drop_table('long_term_goal')
    op.drop_table('work_shift')
