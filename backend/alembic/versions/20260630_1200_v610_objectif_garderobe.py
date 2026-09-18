"""objectif_type + vetement.type_objectif (#garderobe-objectif)

Revision ID: v610objectifgarderobe
Revises: m601musicquality
Create Date: 2026-06-30 12:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "v610objectifgarderobe"
down_revision = "m601musicquality"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "objectif_type",
        sa.Column("nom", sa.String(), primary_key=True),
        sa.Column("ordre", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantite_objectif", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("echelle", sa.JSON(), nullable=True),
    )
    with op.batch_alter_table("vetement") as batch_op:
        batch_op.add_column(sa.Column("type_objectif", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("vetement") as batch_op:
        batch_op.drop_column("type_objectif")
    op.drop_table("objectif_type")
