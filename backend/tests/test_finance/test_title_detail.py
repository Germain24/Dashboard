"""Vue détaillée par titre (prix, P/E, score Buffett, poids, perf)."""

from __future__ import annotations

import datetime as dt
from app.core.timeutil import utcnow

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.models.finance import Position, BuffettRunResult
from app.services.finance import prices
from app.services.finance.portfolio import get_title_detail


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _seed_price(ticker, price):
    prices.clear_cache()
    # Pré-remplit le cache pour la date du jour (le service appelle get_prices() sans date).
    prices.get_prices([ticker], fetcher=lambda t: {ticker: price})


def test_detail_held_title(session):
    session.add(Position(ticker="AAPL", broker="t212", quantite=10, pmu=100.0, devise="USD",
                         updated_at=utcnow()))
    session.add(BuffettRunResult(ticker="AAPL", nom="Apple", secteur="Tech", per=21.0, chance_moat=88.0))
    session.commit()
    _seed_price("AAPL", 190.0)

    d = get_title_detail(session, "aapl")
    assert d["ticker"] == "AAPL"
    assert d["nom"] == "Apple"
    assert d["prix"] == 190.0
    assert d["per"] == 21.0
    assert d["score_buffett"] == 88.0
    assert d["quantite"] == 10
    assert d["pmu"] == 100.0
    assert d["valeur"] == 1900.0
    assert d["pl_pct"] == 90.0  # (190/100 - 1)*100
    assert d["poids_pct"] == 100.0  # seul titre détenu
    assert d["detenu"] is True


def test_detail_not_held_title(session):
    session.add(BuffettRunResult(ticker="NVDA", nom="Nvidia", per=40.0, chance_moat=95.0))
    session.commit()
    _seed_price("NVDA", 900.0)

    d = get_title_detail(session, "NVDA")
    assert d["detenu"] is False
    assert d["quantite"] == 0
    assert d["score_buffett"] == 95.0
    assert d["pl_pct"] == 0.0
