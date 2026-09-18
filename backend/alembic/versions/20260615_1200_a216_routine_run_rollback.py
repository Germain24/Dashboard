"""file d'automatisations : artefacts pour rollback (#216)

Ajoute à routine_run :
- created_ids : JSON des artefacts réversibles ({"notifications":[id], "jobs":[...]})
- rolled_back : run déjà annulé (idempotence du rollback)

Revision ID: a216runrollback
Revises: r217routinerun
Create Date: 2026-06-15 12:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "a216runrollback"
down_revision = "r217routinerun"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "routine_run",
        sa.Column("created_ids", sa.String(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "routine_run",
        sa.Column("rolled_back", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("routine_run", "rolled_back")
    op.drop_column("routine_run", "created_ids")
