"""Réduction des longues séries de snapshots destinées aux graphiques."""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.models.finance import SnapshotPortefeuille, Transaction
from app.services.finance.snapshots import (
    carry_forward_partial_values,
    downsample_history,
    get_history,
    reconcile_invested_history,
)


def test_downsample_history_preserves_size_order_and_endpoints():
    start = dt.date(2020, 1, 1)
    rows = [
        SnapshotPortefeuille(
            date=start + dt.timedelta(days=index),
            valeur=float(index),
            investit=float(index),
        )
        for index in range(10_000)
    ]

    sampled = downsample_history(rows, max_points=1_000)

    assert len(sampled) == 1_000
    assert sampled[0].date == rows[0].date
    assert sampled[-1].date == rows[-1].date
    assert [row.date for row in sampled] == sorted(row.date for row in sampled)


def test_downsample_history_keeps_short_series_unchanged():
    rows = [
        SnapshotPortefeuille(date=dt.date(2026, 7, day), valeur=float(day), investit=float(day))
        for day in range(1, 5)
    ]

    assert downsample_history(rows, max_points=10) is rows


def _cash_flow(day: int, type_: str, amount: float) -> Transaction:
    return Transaction(
        date=dt.datetime(2026, 1, day, 12),
        ticker="CASH",
        broker="Trading212",
        type=type_,
        quantite=1.0,
        prix_unitaire=amount,
    )


def test_reconcile_invested_history_carries_forward_without_withdrawal():
    rows = [
        SnapshotPortefeuille(date=dt.date(2026, 1, 1), valeur=1_100, investit=1_000),
        SnapshotPortefeuille(date=dt.date(2026, 1, 2), valeur=1_050, investit=600),
        SnapshotPortefeuille(date=dt.date(2026, 1, 3), valeur=1_070, investit=600),
    ]

    reconciled = reconcile_invested_history(rows, [])

    assert [row.investit for row in reconciled] == [1_000, 1_000, 1_000]
    # Une lecture ne réécrit pas les données brutes sans migration explicite.
    assert rows[1].investit == 600


def test_reconcile_does_not_double_count_deposit_already_in_reliable_history():
    rows = [
        SnapshotPortefeuille(date=dt.date(2026, 1, 1), valeur=1_100, investit=1_000),
        SnapshotPortefeuille(date=dt.date(2026, 1, 2), valeur=1_300, investit=1_200),
    ]

    reconciled = reconcile_invested_history(rows, [_cash_flow(2, "depot", 200)])

    assert [row.investit for row in reconciled] == [1_000, 1_200]


def test_reconcile_applies_documented_deposit_when_raw_value_is_missing():
    rows = [
        SnapshotPortefeuille(date=dt.date(2026, 1, 1), valeur=1_100, investit=1_000),
        SnapshotPortefeuille(date=dt.date(2026, 1, 2), valeur=1_300, investit=1_000),
    ]

    reconciled = reconcile_invested_history(rows, [_cash_flow(2, "depot", 200)])

    assert [row.investit for row in reconciled] == [1_000, 1_200]


def test_reconcile_applies_documented_withdrawal_when_raw_value_is_stale():
    rows = [
        SnapshotPortefeuille(date=dt.date(2026, 1, 1), valeur=1_100, investit=1_000),
        SnapshotPortefeuille(date=dt.date(2026, 1, 2), valeur=900, investit=1_000),
    ]

    reconciled = reconcile_invested_history(rows, [_cash_flow(2, "retrait", 200)])

    assert [row.investit for row in reconciled] == [1_000, 800]


def test_reconcile_preserves_growth_until_unexplained_source_break():
    rows = [
        SnapshotPortefeuille(date=dt.date(2026, 1, 1), valeur=1_100, investit=1_000),
        SnapshotPortefeuille(date=dt.date(2026, 1, 2), valeur=1_300, investit=1_200),
        SnapshotPortefeuille(date=dt.date(2026, 1, 3), valeur=1_500, investit=1_400),
        # Rupture > 20 % sans retrait : la dernière ancre fiable est 1 400.
        SnapshotPortefeuille(date=dt.date(2026, 1, 4), valeur=1_450, investit=800),
        SnapshotPortefeuille(date=dt.date(2026, 1, 5), valeur=1_460, investit=850),
    ]
    flows = [
        _cash_flow(4, "depot", 50),
        _cash_flow(5, "retrait", 20),
    ]

    reconciled = reconcile_invested_history(rows, flows)

    assert [row.investit for row in reconciled] == [1_000, 1_200, 1_400, 1_450, 1_430]


def test_reconcile_real_history_anchors_21051_then_applies_later_deposits():
    rows = [
        SnapshotPortefeuille(date=dt.date(2026, 5, 3), valeur=26_300, investit=20_850),
        SnapshotPortefeuille(date=dt.date(2026, 5, 15), valeur=27_785, investit=21_051.60),
        SnapshotPortefeuille(date=dt.date(2026, 6, 9), valeur=26_734, investit=15_000),
        SnapshotPortefeuille(date=dt.date(2026, 6, 30), valeur=27_249, investit=15_000),
        SnapshotPortefeuille(date=dt.date(2026, 7, 3), valeur=27_381, investit=15_000),
        SnapshotPortefeuille(date=dt.date(2026, 7, 15), valeur=28_345, investit=16_057),
    ]
    flows = [
        Transaction(
            date=dt.datetime(2026, 5, 29, 12), ticker="CASH", broker="Trading212",
            type="depot", quantite=1, prix_unitaire=100,
        ),
        Transaction(
            date=dt.datetime(2026, 6, 30, 12), ticker="CASH", broker="Trading212",
            type="depot", quantite=1, prix_unitaire=100,
        ),
        Transaction(
            date=dt.datetime(2026, 7, 1, 12), ticker="CASH", broker="Trading212",
            type="depot", quantite=1, prix_unitaire=50,
        ),
    ]

    reconciled = reconcile_invested_history(rows, flows)

    assert [row.investit for row in reconciled] == [
        20_850,
        21_051.60,
        21_151.60,
        21_251.60,
        21_301.60,
        21_301.60,
    ]
    assert rows[2].investit == 15_000


def test_get_history_reconciles_before_applying_recent_limit():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([
            SnapshotPortefeuille(date=dt.date(2026, 1, 1), valeur=1_000, investit=900),
            SnapshotPortefeuille(date=dt.date(2026, 1, 2), valeur=1_100, investit=100),
            SnapshotPortefeuille(date=dt.date(2026, 1, 3), valeur=1_200, investit=100),
            _cash_flow(3, "depot", 50),
        ])
        session.commit()

        recent = get_history(session, limit=1)

    assert len(recent) == 1
    assert recent[0].date == dt.date(2026, 1, 3)
    assert recent[0].investit == 950


def test_partial_account_values_are_carried_forward_without_mutating_raw_rows():
    rows = [
        SnapshotPortefeuille(date=dt.date(2026, 7, 12), valeur=27_468.80, investit=16_100),
        SnapshotPortefeuille(date=dt.date(2026, 7, 13), valeur=861.54, investit=16_100),
        SnapshotPortefeuille(date=dt.date(2026, 7, 14), valeur=859.36, investit=16_100),
        SnapshotPortefeuille(date=dt.date(2026, 7, 15), valeur=28_344.75, investit=16_100),
    ]

    carried = carry_forward_partial_values(rows)

    assert [row.valeur for row in carried] == [
        27_468.80, 27_468.80, 27_468.80, 28_344.75,
    ]
    assert rows[1].valeur == 861.54


def test_manifestly_partial_last_snapshot_is_carried_without_future_recovery():
    rows = [
        SnapshotPortefeuille(date=dt.date(2026, 7, 12), valeur=27_468.80, investit=16_100),
        SnapshotPortefeuille(date=dt.date(2026, 7, 13), valeur=27_510.00, investit=16_100),
        SnapshotPortefeuille(date=dt.date(2026, 7, 14), valeur=861.54, investit=16_100),
    ]

    carried = carry_forward_partial_values(rows)

    assert [row.valeur for row in carried] == [27_468.80, 27_510.00, 27_510.00]
    assert rows[-1].valeur == 861.54


def test_documented_large_withdrawal_is_not_hidden_as_partial_tail():
    rows = [
        SnapshotPortefeuille(date=dt.date(2026, 7, 13), valeur=10_000, investit=9_000),
        SnapshotPortefeuille(date=dt.date(2026, 7, 14), valeur=2_000, investit=1_800),
    ]

    carried = carry_forward_partial_values(rows)

    assert [row.valeur for row in carried] == [10_000, 2_000]
