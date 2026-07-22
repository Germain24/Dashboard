"""Rendement pondéré dans le temps (TWR) + annualisation."""

from __future__ import annotations

import datetime as dt

from app.services.finance.metrics import (
    annualized_capital_return,
    money_weighted_annual_return,
)
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
    assert time_weighted_return([]) == {
        "twr_pct": None,
        "twr_annualise_pct": None,
        "n_jours": 0,
    }
    assert time_weighted_return(
        [(dt.date(2025, 1, 1), 100.0, 100.0)]
    )["twr_pct"] is None


def test_twr_unreliable_cashflow_chain_is_not_published():
    """Une rupture qui implique -29 % en un jour ne doit pas être étiquetée TWR."""
    snaps = [
        (dt.date(2020, 2, 29), 192.78, 280.0),
        (dt.date(2020, 3, 1), 416.78, 560.0),
    ]

    result = time_weighted_return(snaps)

    assert result["twr_pct"] is None
    assert result["twr_annualise_pct"] is None


def test_twr_carries_forward_transient_partial_account_snapshot():
    """Régression réelle : le sous-compte à 861 € ne vaut pas une perte de 97 %."""
    snaps = [
        (dt.date(2026, 7, 12), 27_468.80, 15_000.00),
        (dt.date(2026, 7, 13), 861.54, 1_057.41271976),
        (dt.date(2026, 7, 14), 859.36, 1_057.41271976),
        (dt.date(2026, 7, 15), 28_344.75, 16_057.41271976),
    ]

    result = time_weighted_return(snaps)

    assert result["twr_pct"] is not None
    assert -1.0 < result["twr_pct"] < 0.0


def test_capital_return_cagr_matches_six_year_example():
    cagr = annualized_capital_return(
        valeur=1.7583,
        investit=1.0,
        start_date=dt.date(2020, 1, 1),
        end_date=dt.date(2026, 1, 1),
    )

    assert cagr is not None
    assert 9.8 < cagr < 9.9


def test_money_weighted_return_accounts_for_contribution_timing():
    snapshots = [
        (dt.date(2023, 1, 1), 100.0, 100.0),
        (dt.date(2024, 1, 1), 160.0, 150.0),  # apport de 50 après un an
        (dt.date(2025, 1, 1), 220.0, 150.0),
    ]

    result = money_weighted_annual_return(snapshots)

    assert result is not None
    assert 25.0 < result < 25.8


def test_money_weighted_return_no_contribution_matches_annual_return():
    result = money_weighted_annual_return([
        (dt.date(2025, 1, 1), 100.0, 100.0),
        (dt.date(2026, 1, 1), 110.0, 100.0),
    ])

    assert result is not None
    assert 9.5 < result < 10.5
