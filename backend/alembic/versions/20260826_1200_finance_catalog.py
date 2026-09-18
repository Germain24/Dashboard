"""normalized finance catalog

Revision ID: fcat20260826
Revises: 495cbf46bce0
"""

import sqlalchemy as sa

from alembic import op

revision = "fcat20260826"
down_revision = "495cbf46bce0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finance_instrument",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("isin", sa.String(12)),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("instrument_type", sa.String(), nullable=False),
        sa.Column("domicile_country", sa.String(2)),
        sa.Column("identity_status", sa.String(), nullable=False),
        sa.Column("source", sa.String()),
        sa.Column("source_url", sa.String()),
        sa.Column("source_checked_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_finance_instrument_isin",
        "finance_instrument",
        ["isin"],
        unique=True,
        sqlite_where=sa.text("isin IS NOT NULL"),
    )
    op.create_index(
        "ix_finance_instrument_instrument_type", "finance_instrument", ["instrument_type"]
    )
    op.create_table(
        "finance_listing",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "instrument_id", sa.Integer(), sa.ForeignKey("finance_instrument.id"), nullable=False
        ),
        sa.Column("mic", sa.String(), nullable=False),
        sa.Column("local_symbol", sa.String(), nullable=False),
        sa.Column("yahoo_symbol", sa.String()),
        sa.Column("currency", sa.String(3)),
        sa.Column("primary_market", sa.Boolean(), nullable=False),
        sa.Column("fundamentals_symbol", sa.String()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("mic", "local_symbol", name="uq_finance_listing_mic_symbol"),
    )
    for name, cols in (
        ("ix_finance_listing_instrument_id", ["instrument_id"]),
        ("ix_finance_listing_mic", ["mic"]),
        ("ix_finance_listing_local_symbol", ["local_symbol"]),
        ("ix_finance_listing_yahoo_symbol", ["yahoo_symbol"]),
    ):
        op.create_index(name, "finance_listing", cols)
    op.create_table(
        "finance_broker",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("account_type", sa.String()),
    )
    op.create_index("ix_finance_broker_code", "finance_broker", ["code"], unique=True)
    op.create_table(
        "finance_broker_availability",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("finance_listing.id"), nullable=False),
        sa.Column("broker_id", sa.Integer(), sa.ForeignKey("finance_broker.id"), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("checked_at", sa.DateTime()),
        sa.Column("source", sa.String()),
        sa.Column("source_url", sa.String()),
        sa.Column("source_record_id", sa.String()),
        sa.CheckConstraint("state IN ('TRUE', 'FALSE', 'UNKNOWN')", name="ck_broker_state"),
        sa.UniqueConstraint("listing_id", "broker_id", name="uq_listing_broker_availability"),
    )
    for col in ("listing_id", "broker_id", "state"):
        op.create_index(
            f"ix_finance_broker_availability_{col}", "finance_broker_availability", [col]
        )
    op.create_table(
        "finance_market_observation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("finance_listing.id"), nullable=False),
        sa.Column("observed_at", sa.DateTime()),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.Column("price", sa.Float()),
        sa.Column("price_currency", sa.String(3)),
        sa.Column("average_volume_shares", sa.Float()),
        sa.Column("average_turnover_value", sa.Float()),
        sa.Column("turnover_currency", sa.String(3)),
        sa.Column("source", sa.String()),
        sa.Column("source_url", sa.String()),
    )
    op.create_index(
        "ix_finance_market_observation_listing_id", "finance_market_observation", ["listing_id"]
    )
    op.create_index(
        "ix_finance_market_observation_observed_at", "finance_market_observation", ["observed_at"]
    )
    op.create_table(
        "finance_fundamental_observation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "instrument_id", sa.Integer(), sa.ForeignKey("finance_instrument.id"), nullable=False
        ),
        sa.Column("observed_at", sa.DateTime()),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.Column("eps", sa.Float()),
        sa.Column("per", sa.Float()),
        sa.Column("growth", sa.Float()),
        sa.Column("peg", sa.Float()),
        sa.Column("sector", sa.String()),
        sa.Column("country", sa.String()),
        sa.Column("source", sa.String()),
        sa.Column("source_url", sa.String()),
    )
    op.create_index(
        "ix_finance_fundamental_observation_instrument_id",
        "finance_fundamental_observation",
        ["instrument_id"],
    )
    op.create_index(
        "ix_finance_fundamental_observation_observed_at",
        "finance_fundamental_observation",
        ["observed_at"],
    )
    op.create_table(
        "finance_index",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("canonical_code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("source", sa.String()),
        sa.Column("source_url", sa.String()),
    )
    op.create_index(
        "ix_finance_index_canonical_code", "finance_index", ["canonical_code"], unique=True
    )
    op.create_table(
        "finance_index_constituent",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("index_id", sa.Integer(), sa.ForeignKey("finance_index.id"), nullable=False),
        sa.Column(
            "instrument_id", sa.Integer(), sa.ForeignKey("finance_instrument.id"), nullable=False
        ),
        sa.Column("weight", sa.Float()),
        sa.Column("as_of", sa.Date()),
        sa.Column("source", sa.String()),
        sa.Column("source_url", sa.String()),
        sa.UniqueConstraint("index_id", "instrument_id", name="uq_index_instrument"),
    )
    op.create_index(
        "ix_finance_index_constituent_index_id", "finance_index_constituent", ["index_id"]
    )
    op.create_index(
        "ix_finance_index_constituent_instrument_id", "finance_index_constituent", ["instrument_id"]
    )


def downgrade() -> None:
    for table in (
        "finance_index_constituent",
        "finance_index",
        "finance_fundamental_observation",
        "finance_market_observation",
        "finance_broker_availability",
        "finance_broker",
        "finance_listing",
        "finance_instrument",
    ):
        op.drop_table(table)
