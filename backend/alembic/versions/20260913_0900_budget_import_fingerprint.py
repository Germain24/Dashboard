"""Persist source identities and idempotency fingerprints for budget imports.

Revision ID: budgetimport20260913
Revises: fcatmeta20260827
"""

import sqlalchemy as sa

from alembic import op

revision = "budgetimport20260913"
down_revision = "fcatmeta20260827"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable fields preserve all existing/manual transactions. Existing rows
    # are deliberately not backfilled because their original source is unknown.
    with op.batch_alter_table("budget_transaction") as batch:
        batch.add_column(sa.Column("import_source", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("import_external_id", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("import_fingerprint", sa.String(length=64), nullable=True))
    op.create_index(
        "ix_budget_transaction_import_fingerprint",
        "budget_transaction",
        ["import_fingerprint"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_budget_transaction_import_fingerprint", table_name="budget_transaction")
    with op.batch_alter_table("budget_transaction") as batch:
        batch.drop_column("import_fingerprint")
        batch.drop_column("import_external_id")
        batch.drop_column("import_source")
