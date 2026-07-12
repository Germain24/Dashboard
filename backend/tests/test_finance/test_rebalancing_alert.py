"""Alerte de rééquilibrage : écart poids actuel/cible au-delà du seuil."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.models.finance import BuffettRun, BuffettRunResult, Transaction
from app.services.finance import portfolio_state, prices
from app.services.finance.buffett.config import Config
from app.services.finance.rebalancing import (
    _ecart_alerte,
    REBALANCE_ALERT_THRESHOLD_PCT,
    compute_rebalancing_diff,
)


def test_ecart_within_threshold_no_alert():
    ecart, alerte = _ecart_alerte(12.0, 10.0, REBALANCE_ALERT_THRESHOLD_PCT)
    assert ecart == 2.0
    assert alerte is False


def test_ecart_above_threshold_triggers_alert():
    ecart, alerte = _ecart_alerte(18.0, 10.0, REBALANCE_ALERT_THRESHOLD_PCT)
    assert ecart == 8.0
    assert alerte is True


def test_underweight_above_threshold_triggers_alert():
    ecart, alerte = _ecart_alerte(2.0, 10.0, REBALANCE_ALERT_THRESHOLD_PCT)
    assert ecart == -8.0
    assert alerte is True


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_compute_rebalancing_diff_uses_ledger_positions(session, monkeypatch):
    """Régression : sans transactions dans la table Position (mode ledger), le
    diff de rééquilibrage doit refléter la position dérivée des Transaction,
    pas 0 (ce qui arrivait avant le fix en lisant Position directement)."""
    from app.services.finance import rebalancing as rebalancing_mod

    portfolio_state.invalidate_state()
    prices.clear_cache()
    prices.get_prices(["AAPL"], fetcher=lambda t: {"AAPL": 150.0})

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"Trading212": 1000.0})
    monkeypatch.setattr(rebalancing_mod, "_fetch_prices", lambda tickers: {"AAPL": 150.0})

    session.add(Transaction(
        ticker="AAPL", broker="Trading212", type="achat",
        quantite=10, prix_unitaire=100.0, frais=0.0,
        date=dt.datetime(2026, 1, 1),
    ))
    run = BuffettRun(run_date=dt.date(2026, 1, 15), statut="termine")
    session.add(run)
    session.commit()
    session.refresh(run)

    session.add(BuffettRunResult(
        run_id=run.id, ticker="AAPL", nom="Apple", prix=140.0,
        allocation_pct=50.0, broker_cible="Trading212",
    ))
    session.commit()

    diff = compute_rebalancing_diff(session)
    assert diff is not None
    assert len(diff.lignes) == 1
    ligne = diff.lignes[0]
    assert ligne.ticker == "AAPL"
    # Dérivé du ledger (10 actions à 150 = 1500), PAS 0 comme si Position était vide.
    assert ligne.quantite_actuelle == 10
    assert ligne.valeur_actuelle_eur == 1500.0
    # Cible = 50% de 1000 = 500 € < valeur actuelle 1500 € -> vendre.
    assert ligne.valeur_cible_eur == 500.0
    assert ligne.action == "VENDRE"
