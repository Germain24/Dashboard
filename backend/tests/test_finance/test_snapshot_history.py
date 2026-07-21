"""Réduction des longues séries de snapshots destinées aux graphiques."""

from __future__ import annotations

import datetime as dt

from app.models.finance import SnapshotPortefeuille
from app.services.finance.snapshots import downsample_history


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
