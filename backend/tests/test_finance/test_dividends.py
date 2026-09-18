"""Suivi des dividendes reçus."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.models.finance import Transaction
from app.services.finance.transactions import get_dividends_summary


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _div(session, ticker, date, qte, prix):
    session.add(Transaction(ticker=ticker, type="dividende",
                            date=dt.datetime.combine(date, dt.time.min),
                            quantite=qte, prix_unitaire=prix, devise="EUR"))


def test_dividends_summary(session):
    _div(session, "AAPL", dt.date(2026, 1, 15), 10, 0.5)   # 5 €
    _div(session, "AAPL", dt.date(2026, 4, 15), 10, 0.6)   # 6 €
    _div(session, "MSFT", dt.date(2026, 1, 20), 5, 1.0)    # 5 €
    # une transaction d'achat ne doit pas compter
    session.add(Transaction(ticker="AAPL", type="achat",
                            date=dt.datetime(2026, 1, 1), quantite=10, prix_unitaire=100.0, devise="EUR"))
    session.commit()

    s = get_dividends_summary(session)
    assert s["total_recu"] == 16.0
    assert s["n_versements"] == 3
    assert s["par_ticker"]["AAPL"] == 11.0
    assert s["par_ticker"]["MSFT"] == 5.0
    assert s["par_mois"]["2026-01"] == 10.0
    assert s["par_mois"]["2026-04"] == 6.0


def test_no_dividends(session):
    s = get_dividends_summary(session)
    assert s["total_recu"] == 0
    assert s["n_versements"] == 0
    assert s["lignes"] == []
