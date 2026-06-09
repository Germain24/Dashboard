"""robot module: conversations, messages, actions (#153/#158/#163)

Revision ID: n153robottables
Revises: m144pagecourante
Create Date: 2026-06-08 17:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "n153robottables"
down_revision = "m144pagecourante"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "robot_conversation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("titre", sa.String(), nullable=False, server_default="Nouvelle conversation"),
        sa.Column("model", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_creation_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_table(
        "robot_message",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("robot_conversation.id"), nullable=False, index=True),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "robot_action",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("robot_conversation.id"), nullable=True, index=True),
        sa.Column("tool", sa.String(), nullable=False),
        sa.Column("args", sa.String(), nullable=False, server_default="{}"),
        sa.Column("statut", sa.String(), nullable=False, server_default="auto"),
        sa.Column("result", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("robot_action")
    op.drop_table("robot_message")
    op.drop_table("robot_conversation")
