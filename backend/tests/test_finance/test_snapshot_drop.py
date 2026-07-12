"""Détection de chute de valeur du portefeuille (alerte snapshot)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.models.finance import Transaction
from app.services.finance import portfolio_state, prices
from app.services.finance.snapshots import drop_alert_pct, take_snapshot_now


def test_big_drop_triggers():
    assert drop_alert_pct(100.0, 92.0, seuil_pct=5.0) == 8.0


def test_small_drop_no_alert():
    assert drop_alert_pct(100.0, 97.0, seuil_pct=5.0) is None


def test_gain_no_alert():
    assert drop_alert_pct(100.0, 110.0, seuil_pct=5.0) is None


def test_invalid_prev():
    assert drop_alert_pct(0.0, 50.0) is None
    assert drop_alert_pct(None, 50.0) is None


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_take_snapshot_now_from_ledger_positions(session):
    """Régression : sans lignes dans la table Position (mode ledger), le
    snapshot doit refléter la position dérivée des Transaction (via
    get_positions()), pas rester vide/None comme si on lisait Position
    directement."""
    portfolio_state.invalidate_state()
    prices.clear_cache()
    prices.get_prices(["AAPL"], fetcher=lambda t: {"AAPL": 150.0})

    session.add(Transaction(
        ticker="AAPL", broker="t212", type="achat",
        quantite=10, prix_unitaire=100.0, frais=0.0,
        date=dt.datetime(2026, 1, 1),
    ))
    session.commit()

    snap = take_snapshot_now(session)
    assert snap is not None
    assert snap.valeur == 1500.0    # 10 * 150
    assert snap.investit == 1000.0  # 10 * 100 (pmu/acb)
    assert snap.date == dt.date.today()
