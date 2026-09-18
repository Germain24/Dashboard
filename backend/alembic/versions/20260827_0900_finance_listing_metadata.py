"""listing metadata for normalized finance catalog

Revision ID: fcatmeta20260827
Revises: fcat20260826
"""

import sqlalchemy as sa

from alembic import op

revision = "fcatmeta20260827"
down_revision = "fcat20260826"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("finance_listing") as batch:
        batch.add_column(sa.Column("metadata_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("finance_listing") as batch:
        batch.drop_column("metadata_json")
