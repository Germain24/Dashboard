"""Les métriques ne sont publiées que sur la période réellement documentée.

L'historique antérieur au premier relevé broker est une reconstruction : dans
la base réelle, elle perd exactement 20 % de chaque versement (280 € versés
n'augmentent la valeur que de 224 €, médiane 0,80 sur 59 mois). Chaînée sur
59 apports mensuels, cette fuite écrase l'indice de richesse à 0,585 et produit
un drawdown de 63,7 %, un Sharpe négatif et un CAGR de 4,5 % alors que le
portefeuille est en plus-value.

Décision : rendement, Sharpe, Sortino, volatilité et drawdown ne portent que sur
la fenêtre couverte par les documents (première transaction du grand livre). Le
graphique, lui, conserve tout l'historique.
"""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.models.finance import SnapshotPortefeuille, Transaction
from app.services.finance.portfolio import get_perf_metrics
from app.services.finance.snapshots import documented_history_start, get_history


def _session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed(session: Session) -> None:
    """Backfill fuyard (20 % perdus par apport) puis période documentée saine."""
    start = dt.date(2020, 1, 1)
    valeur, investit = 100.0, 100.0
    day = start
    while day < dt.date(2025, 6, 1):
        if day.day == 1 and day != start:
            investit += 100.0
            valeur += 80.0  # la fuite de 20 % du backfill réel
        session.add(
            SnapshotPortefeuille(date=day, valeur=round(valeur, 2), investit=investit)
        )
        day += dt.timedelta(days=1)

    # Premier document broker : à partir d'ici, les apports entrent en entier.
    documented_start = dt.date(2025, 6, 1)
    session.add(
        Transaction(
            date=dt.datetime(2025, 6, 1, 10, 0),
            type="depot",
            ticker="CASH",
            quantite=1,
            prix_unitaire=100.0,
        )
    )
    day = documented_start
    while day <= dt.date(2026, 6, 1):
        if day.day == 1 and day != documented_start:
            investit += 100.0
            valeur += 100.0
        valeur *= 1.0002
        session.add(
            SnapshotPortefeuille(date=day, valeur=round(valeur, 2), investit=investit)
        )
        day += dt.timedelta(days=1)
    session.commit()


def test_documented_start_is_the_first_ledger_transaction():
    with _session() as session:
        _seed(session)
        assert documented_history_start(session) == dt.date(2025, 6, 1)


def test_no_transactions_means_no_documented_window():
    with _session() as session:
        session.add(
            SnapshotPortefeuille(date=dt.date(2024, 1, 1), valeur=10.0, investit=10.0)
        )
        session.commit()
        assert documented_history_start(session) is None


def test_chart_history_keeps_the_full_reconstructed_series():
    """Le graphique ne doit rien perdre : seule la publication des ratios est
    restreinte."""
    with _session() as session:
        _seed(session)
        rows = get_history(session, limit=10_000)
        assert rows[0].date == dt.date(2020, 1, 1)


def test_perf_metrics_ignore_the_leaky_backfill():
    with _session() as session:
        _seed(session)
        metrics = get_perf_metrics(session)

    assert metrics["periode_debut"] == "2025-06-01"
    # La fuite du backfill produisait un drawdown massif et un rendement négatif
    # sur une série pourtant croissante.
    assert metrics["max_drawdown_pct"] < 5.0
    assert metrics["cagr_pct"] is not None
    assert metrics["cagr_pct"] > 0.0


def test_valeur_and_investit_stay_on_the_latest_snapshot():
    """La fenêtre ne tronque que les métriques : le patrimoine affiché reste le
    dernier état connu, capital inclus."""
    with _session() as session:
        _seed(session)
        rows = get_history(session, limit=10_000)
        metrics = get_perf_metrics(session)

    assert metrics["valeur"] == rows[-1].valeur
    assert metrics["investit"] == rows[-1].investit
