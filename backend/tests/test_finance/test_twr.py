"""Rendement pondéré dans le temps (TWR) + annualisation."""

from __future__ import annotations

import datetime as dt

from app.services.finance.portfolio import time_weighted_return


def test_twr_simple_no_contribution():
    snaps = [
        (dt.date(2025, 1, 1), 100.0, 100.0),
        (dt.date(2026, 1, 1), 110.0, 100.0),  # +10 %, aucun apport
    ]
    r = time_weighted_return(snaps)
    assert round(r["twr_pct"], 2) == 10.0
    # ~365 j -> annualisé ≈ 10 %
    assert 9.5 <= r["twr_annualise_pct"] <= 10.5


def test_twr_removes_contribution_effect():
    # valeur double mais 90 vient d'un apport -> la perf "vraie" est +10 %
    snaps = [
        (dt.date(2025, 1, 1), 100.0, 100.0),
        (dt.date(2026, 1, 1), 200.0, 190.0),  # apport net = 90
    ]
    r = time_weighted_return(snaps)
    assert round(r["twr_pct"], 2) == 10.0


def test_twr_empty_or_single():
    assert time_weighted_return([]) == {"twr_pct": 0.0, "twr_annualise_pct": 0.0, "n_jours": 0}
    assert time_weighted_return([(dt.date(2025, 1, 1), 100.0, 100.0)])["twr_pct"] == 0.0
