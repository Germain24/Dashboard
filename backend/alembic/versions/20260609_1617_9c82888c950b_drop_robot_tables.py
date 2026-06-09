"""drop robot tables

Revision ID: 9c82888c950b
Revises: 262e83c85856
Create Date: 2026-06-09 16:17:17.813755
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '9c82888c950b'
down_revision: Union[str, None] = '262e83c85856'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Module Robot supprimé (pas d'IA dans le dashboard) — on retire ses tables.
    # Enfants d'abord (FK vers robot_conversation), puis la table parente.
    # Sous SQLite, les index sont supprimés avec leur table.
    op.drop_table("robot_message")
    op.drop_table("robot_action")
    op.drop_table("robot_conversation")


def downgrade() -> None:
    # Suppression définitive : le module Robot a été retiré, pas de retour arrière.
    raise NotImplementedError("Suppression du module Robot non réversible")
