"""Détection de chute de valeur du portefeuille (alerte snapshot)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.models.finance import SnapshotPortefeuille, Transaction
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
    portfolio_state.invalidate_state()
    prices.clear_cache()
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    portfolio_state.invalidate_state()
    prices.clear_cache()


def test_take_snapshot_now_from_ledger_positions(session):
    """Régression : sans lignes dans la table Position (mode ledger), le
    snapshot doit refléter la position dérivée des Transaction (via
    get_positions()), pas rester vide/None comme si on lisait Position
    directement."""
    portfolio_state.invalidate_state()
    prices.clear_cache()
    prices.get_prices(["AAPL"], fetcher=lambda t: {"AAPL": 150.0})

    session.add_all([
        Transaction(
            ticker="CASH",
            broker="t212",
            type="depot",
            quantite=1.0,
            prix_unitaire=1000.0,
            frais=0.0,
            date=dt.datetime(2026, 1, 1),
        ),
        Transaction(
            ticker="AAPL",
            broker="t212",
            type="achat",
            quantite=10,
            prix_unitaire=100.0,
            frais=0.0,
            date=dt.datetime(2026, 1, 1),
        ),
    ])
    session.commit()

    snap = take_snapshot_now(session)
    assert snap is not None
    assert snap.valeur == 1500.0  # 10 * 150
    assert snap.investit == 1000.0  # 10 * 100 (pmu/acb)
    assert snap.date == dt.date.today()


def test_take_snapshot_now_rejects_position_without_price(session, monkeypatch):
    monkeypatch.setattr(
        "app.services.finance.portfolio_state.get_portfolio_state",
        lambda _session: {
            "positions": [{
                "ticker": "CW8.PA",
                "quantite": 10.0,
                "prix": 0.0,
                "valeur": 0.0,
                "acb": 500.0,
            }],
            "cash_total": 0.0,
            "valeur_totale": 0.0,
            "investi_net": 5_000.0,
        },
    )

    assert take_snapshot_now(session) is None


def test_snapshot_invested_does_not_drop_after_sale_without_withdrawal(
    session, monkeypatch,
):
    today = dt.date.today()
    session.add(
        SnapshotPortefeuille(
            date=today - dt.timedelta(days=1),
            valeur=1_100.0,
            investit=1_000.0,
        )
    )
    # La vente réduit le coût des positions ouvertes, mais aucun euro n'est
    # sorti du compte broker.
    session.add(
        Transaction(
            date=dt.datetime.combine(today, dt.time(10)),
            ticker="AAPL",
            broker="Trading212",
            type="vente",
            quantite=5,
            prix_unitaire=120.0,
        )
    )
    session.commit()
    monkeypatch.setattr(
        "app.services.finance.portfolio_state.get_portfolio_state",
        lambda _session: {
            "positions": [{
                "ticker": "AAPL", "quantite": 5.0, "prix": 120.0,
                "valeur": 600.0, "acb": 100.0,
            }],
            "cash_total": 0.0,
            "valeur_totale": 600.0,
            "investi_net": 0.0,
        },
    )

    snap = take_snapshot_now(session)

    assert snap is not None
    assert snap.investit == 1_000.0


def test_snapshot_invested_changes_only_by_new_documented_cash_flow(
    session, monkeypatch,
):
    today = dt.date.today()
    session.add(
        SnapshotPortefeuille(
            date=today - dt.timedelta(days=1),
            valeur=1_100.0,
            investit=1_000.0,
        )
    )
    session.add_all([
        Transaction(
            date=dt.datetime.combine(today, dt.time(9)),
            ticker="CASH", broker="Trading212", type="depot",
            quantite=1.0, prix_unitaire=200.0,
        ),
        Transaction(
            date=dt.datetime.combine(today, dt.time(10)),
            ticker="AAPL", broker="Trading212", type="achat",
            quantite=1.0, prix_unitaire=150.0,
        ),
    ])
    session.commit()
    monkeypatch.setattr(
        "app.services.finance.portfolio_state.get_portfolio_state",
        lambda _session: {
            "positions": [{
                "ticker": "AAPL", "quantite": 1.0, "prix": 160.0,
                "valeur": 160.0, "acb": 150.0,
            }],
            "cash_total": 50.0,
            "valeur_totale": 210.0,
            "investi_net": 200.0,
        },
    )

    snap = take_snapshot_now(session)

    assert snap is not None
    assert snap.investit == 1_200.0
    assert snap.valeur == 210.0


def test_snapshot_continues_last_reconciled_anchor_not_current_pmu(
    session, monkeypatch,
):
    today = dt.date.today()
    session.add_all([
        SnapshotPortefeuille(
            date=today - dt.timedelta(days=10),
            valeur=27_785.0,
            investit=21_051.60,
        ),
        # Rupture de source brute, sans retrait.
        SnapshotPortefeuille(
            date=today - dt.timedelta(days=2),
            valeur=27_000.0,
            investit=15_000.0,
        ),
        Transaction(
            date=dt.datetime.combine(today - dt.timedelta(days=1), dt.time(12)),
            ticker="CASH",
            broker="Trading212",
            type="depot",
            quantite=1.0,
            prix_unitaire=100.0,
        ),
    ])
    session.commit()
    monkeypatch.setattr(
        "app.services.finance.portfolio_state.get_portfolio_state",
        lambda _session: {
            "positions": [{
                "ticker": "CW8.PA", "quantite": 1.0, "prix": 700.0,
                "valeur": 700.0, "acb": 10.0,
            }],
            "cash_total": 100.0,
            "valeur_totale": 800.0,
            "investi_net": 100.0,
        },
    )

    snap = take_snapshot_now(session)

    assert snap is not None
    assert snap.investit == 21_151.60
