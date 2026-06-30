"""vetement.image : chemin pixel art relatif (#garderobe-pixelart)

Revision ID: i620garderobeimage
Revises: v610objectifgarderobe
Create Date: 2026-06-30 14:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "i620garderobeimage"
down_revision = "v610objectifgarderobe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("vetement") as batch_op:
        batch_op.add_column(sa.Column("image", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("vetement") as batch_op:
        batch_op.drop_column("image")
