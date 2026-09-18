"""Catalogue financier normalisé, source de vérité des instruments et cotations."""

import datetime as dt

from sqlalchemy import JSON, CheckConstraint, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.timeutil import utcnow


class FinanceInstrument(SQLModel, table=True):
    __tablename__ = "finance_instrument"

    id: int | None = Field(default=None, primary_key=True)
    isin: str | None = Field(default=None, index=True, max_length=12)
    name: str
    instrument_type: str = Field(default="UNKNOWN", index=True)
    domicile_country: str | None = Field(default=None, max_length=2)
    identity_status: str = Field(default="UNVERIFIED")
    source: str | None = None
    source_url: str | None = None
    source_checked_at: dt.datetime | None = None
    created_at: dt.datetime = Field(default_factory=utcnow)
    updated_at: dt.datetime = Field(default_factory=utcnow)


class FinanceListing(SQLModel, table=True):
    __tablename__ = "finance_listing"
    __table_args__ = (
        UniqueConstraint("mic", "local_symbol", name="uq_finance_listing_mic_symbol"),
    )

    id: int | None = Field(default=None, primary_key=True)
    instrument_id: int = Field(foreign_key="finance_instrument.id", index=True)
    mic: str = Field(default="UNKNOWN", index=True)
    local_symbol: str = Field(index=True)
    yahoo_symbol: str | None = Field(default=None, index=True)
    currency: str | None = Field(default=None, max_length=3)
    primary_market: bool = False
    fundamentals_symbol: str | None = None
    metadata_json: dict | None = Field(default=None, sa_column=Column(JSON))
    created_at: dt.datetime = Field(default_factory=utcnow)
    updated_at: dt.datetime = Field(default_factory=utcnow)


class FinanceBroker(SQLModel, table=True):
    __tablename__ = "finance_broker"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True)
    label: str
    account_type: str | None = None


class FinanceBrokerAvailability(SQLModel, table=True):
    __tablename__ = "finance_broker_availability"
    __table_args__ = (
        UniqueConstraint("listing_id", "broker_id", name="uq_listing_broker_availability"),
        CheckConstraint("state IN ('TRUE', 'FALSE', 'UNKNOWN')", name="ck_broker_state"),
    )

    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="finance_listing.id", index=True)
    broker_id: int = Field(foreign_key="finance_broker.id", index=True)
    state: str = Field(default="UNKNOWN", index=True)
    checked_at: dt.datetime | None = None
    source: str | None = None
    source_url: str | None = None
    source_record_id: str | None = None


class FinanceMarketObservation(SQLModel, table=True):
    __tablename__ = "finance_market_observation"

    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="finance_listing.id", index=True)
    observed_at: dt.datetime | None = Field(default=None, index=True)
    imported_at: dt.datetime = Field(default_factory=utcnow)
    price: float | None = None
    price_currency: str | None = Field(default=None, max_length=3)
    average_volume_shares: float | None = None
    average_turnover_value: float | None = None
    turnover_currency: str | None = Field(default=None, max_length=3)
    source: str | None = None
    source_url: str | None = None


class FinanceFundamentalObservation(SQLModel, table=True):
    __tablename__ = "finance_fundamental_observation"

    id: int | None = Field(default=None, primary_key=True)
    instrument_id: int = Field(foreign_key="finance_instrument.id", index=True)
    observed_at: dt.datetime | None = Field(default=None, index=True)
    imported_at: dt.datetime = Field(default_factory=utcnow)
    eps: float | None = None
    per: float | None = None
    growth: float | None = None
    peg: float | None = None
    sector: str | None = None
    country: str | None = None
    source: str | None = None
    source_url: str | None = None


class FinanceIndex(SQLModel, table=True):
    __tablename__ = "finance_index"

    id: int | None = Field(default=None, primary_key=True)
    canonical_code: str = Field(unique=True, index=True)
    name: str
    source: str | None = None
    source_url: str | None = None


class FinanceIndexConstituent(SQLModel, table=True):
    __tablename__ = "finance_index_constituent"
    __table_args__ = (UniqueConstraint("index_id", "instrument_id", name="uq_index_instrument"),)

    id: int | None = Field(default=None, primary_key=True)
    index_id: int = Field(foreign_key="finance_index.id", index=True)
    instrument_id: int = Field(foreign_key="finance_instrument.id", index=True)
    weight: float | None = None
    as_of: dt.date | None = None
    source: str | None = None
    source_url: str | None = None
