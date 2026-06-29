"""music_track : colonnes qualité audio + dispo Qobuz (#musique)

Revision ID: m601musicquality
Revises: q257patrimoinesnap
Create Date: 2026-06-29 12:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "m601musicquality"
down_revision = "q257patrimoinesnap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("music_track") as batch_op:
        batch_op.add_column(sa.Column("bitrate_kbps", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("sample_rate_hz", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("bits_per_sample", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("qobuz_available", sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("music_track") as batch_op:
        batch_op.drop_column("qobuz_available")
        batch_op.drop_column("bits_per_sample")
        batch_op.drop_column("sample_rate_hz")
        batch_op.drop_column("bitrate_kbps")
