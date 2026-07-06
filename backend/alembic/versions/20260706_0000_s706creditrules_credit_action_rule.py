"""credit_action_rule + simplification credit_profile (#marge-credit v2)

Revision ID: s706creditrules
Revises: r705creditmargin
Create Date: 2026-07-06 00:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "s706creditrules"
down_revision = "r705creditmargin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_action_rule",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seuil_score", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("montant_estime", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("credit_profile", schema=None) as batch_op:
        batch_op.drop_column("revenu_annuel")
        batch_op.drop_column("date_arrivee_canada")


def downgrade() -> None:
    with op.batch_alter_table("credit_profile", schema=None) as batch_op:
        batch_op.add_column(sa.Column("date_arrivee_canada", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("revenu_annuel", sa.Float(), nullable=True))
    op.drop_table("credit_action_rule")
