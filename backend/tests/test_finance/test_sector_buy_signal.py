from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.finance.buffett.scoring_pure import compute_comparable_peg
from app.services.finance.buffett.sector_buy_signal import (
    apply_sector_percentile_buy_signal,
)


def _row(
    ticker: str,
    sector: str,
    per: float | None,
    peg: float | None,
    *,
    score: float = 85.0,
    growth: float | None = 10.0,
):
    return SimpleNamespace(
        ticker=ticker,
        secteur=sector,
        per=per,
        peg=peg,
        croissance=growth,
        chance_moat=score,
        achat=True,
        secteurs_extra=None,
    )


def test_sector_medians_are_the_only_action_buy_thresholds():
    rows = [
        _row("T1", "Technology", 10.0, 1.5),
        _row("T2", "Technology", 20.0, 1.0),
        _row("T3", "Technology", 30.0, 0.5),
    ]
    diagnostics = apply_sector_percentile_buy_signal(rows, min_sector_size=3)
    tech = diagnostics["sectors"]["Technologie"]
    assert tech["per_max"] == pytest.approx(20.0)
    assert tech["peg_max"] == pytest.approx(1.0)
    assert [row.achat for row in rows] == [False, True, False]
    assert [row.chance_moat for row in rows] == [85.0, 85.0, 85.0]


def test_missing_peg_and_unreliable_growth_are_excluded():
    rows = [
        _row("OK", "Healthcare", 5.0, 0.5),
        _row("MISSING", "Healthcare", 8.0, None),
        _row("EXTREME", "Healthcare", 7.0, 0.2, growth=75.0),
    ]
    diagnostics = apply_sector_percentile_buy_signal(rows, min_sector_size=1)
    assert rows[0].achat is True
    assert rows[1].achat is False
    assert rows[2].achat is False
    assert diagnostics["excluded_missing_peg"] == 2


def test_small_sector_uses_global_medians_and_etf_stays_eligible():
    rows = [
        _row("TECH", "Technology", 10.0, 0.5),
        _row("HEALTH", "Healthcare", 30.0, 1.5),
        _row("ETF1", "ETF", None, None, score=200.0, growth=None),
    ]
    diagnostics = apply_sector_percentile_buy_signal(
        rows,
        etf_tickers={"ETF1"},
        min_sector_size=20,
    )
    assert diagnostics["global"]["per_max"] == pytest.approx(20.0)
    assert diagnostics["global"]["peg_max"] == pytest.approx(1.0)
    assert rows[0].achat is True
    assert rows[1].achat is False
    assert rows[2].achat is True


def test_forced_score_is_not_mistaken_for_an_etf():
    rows = [
        _row("EXPENSIVE", "Technology", 100.0, 5.0, score=200.0),
        _row("NORMAL", "Technology", 10.0, 0.5),
    ]
    apply_sector_percentile_buy_signal(rows, min_sector_size=2)
    assert rows[0].achat is False
    assert rows[0].secteurs_extra["buy_signal"]["reason"] == "above_sector_median"


def test_comparable_peg_uses_forecast_or_history_selected_upstream():
    assert compute_comparable_peg(
        18.0,
        0.12,
        growth_reliable=True,
    ) == pytest.approx(1.5)
    # Croissance plafonnée par PEG_GROWTH_CAP dans le dénominateur (valeur lue
    # depuis la constante : le plafond a déjà été resserré une fois).
    from app.services.finance.buffett.scoring_pure import PEG_GROWTH_CAP

    assert compute_comparable_peg(
        18.0,
        0.80,
        growth_reliable=True,
    ) == pytest.approx(18.0 / (PEG_GROWTH_CAP * 100.0))
    assert compute_comparable_peg(18.0, 0.80, growth_reliable=False) is None


def _row_with_valuation(ticker, sector, valuation, *, per=20.0, peg=1.5, growth=10.0):
    row = _row(ticker, sector, per, peg, growth=growth)
    row.secteurs_extra = {"valuation": valuation}
    return row


def test_specialised_metric_is_used_when_the_sector_is_well_covered():
    """25 REIT tous dotés d'un P/FFO : le secteur bascule sur le profil immobilier."""
    rows = [
        _row_with_valuation(
            f"REIT{i}", "Real Estate",
            {"p_ffo": float(10 + i), "peg_ffo": 1.0 + i / 100.0},
        )
        for i in range(25)
    ]

    diagnostics = apply_sector_percentile_buy_signal(
        rows, percentile=0.50, min_sector_size=20, profiles_enabled=True
    )

    sector = diagnostics["sectors"]["Immobilier"]
    assert sector["profile"] == "immobilier"
    assert sector["profile_fallback"] is None
    assert sector["value_metric"] == "p_ffo"
    # Le seuil porte bien sur le P/FFO (médiane 22), pas sur le PER (tous à 20).
    assert sector["per_max"] == pytest.approx(22.0)


def test_sector_degrades_to_standard_when_the_metric_is_too_sparse():
    """5 P/FFO sur 25 : un quantile calculé là-dessus rejetterait les 20 autres."""
    rows = [
        _row_with_valuation(
            f"REIT{i}", "Real Estate",
            {"p_ffo": 12.0, "peg_ffo": 1.0} if i < 5 else {},
            per=float(10 + i),
        )
        for i in range(25)
    ]

    diagnostics = apply_sector_percentile_buy_signal(
        rows, percentile=0.50, min_sector_size=20, profiles_enabled=True,
        min_metric_coverage=0.60,
    )

    sector = diagnostics["sectors"]["Immobilier"]
    assert sector["profile"] == "standard"
    assert sector["profile_fallback"] == "standard"
    assert sector["coverage"] == pytest.approx(0.20)
    assert sector["value_metric"] == "per"


def test_partial_specialised_coverage_falls_back_per_title_only():
    """Un échantillon spécialisé suffisant reste actif malgré une couverture < 60 %."""
    rows = [
        _row_with_valuation(
            f"REIT{i}",
            "Real Estate",
            {"p_ffo": float(10 + i), "peg_ffo": 0.5 + i / 100.0}
            if i < 12
            else {},
            per=float(10 + i),
            peg=0.5 + i / 100.0,
        )
        for i in range(25)
    ]

    diagnostics = apply_sector_percentile_buy_signal(
        rows,
        percentile=0.50,
        min_sector_size=10,
        profiles_enabled=True,
        min_metric_coverage=0.60,
    )

    sector = diagnostics["sectors"]["Immobilier"]
    assert sector["profile"] == "immobilier"
    assert sector["profile_fallback"] == "per_title_standard"
    assert sector["coverage"] == pytest.approx(12 / 25)
    assert rows[0].secteurs_extra["buy_signal"]["value_metric"] == "p_ffo"
    assert rows[0].secteurs_extra["buy_signal"]["per_title_profile_fallback"] is False
    assert rows[-1].secteurs_extra["buy_signal"]["value_metric"] == "per"
    assert rows[-1].secteurs_extra["buy_signal"]["per_title_profile_fallback"] is True


def test_specialised_values_never_pollute_the_global_pool():
    """Le repli global reste en PER/PEG, sinon on comparerait des P/FFO à des PER."""
    rows = [
        _row_with_valuation(
            f"REIT{i}", "Real Estate",
            {"p_ffo": 999.0, "peg_ffo": 9.9}, per=10.0, peg=1.0,
        )
        for i in range(25)
    ]

    diagnostics = apply_sector_percentile_buy_signal(
        rows, percentile=0.50, min_sector_size=20, profiles_enabled=True
    )

    assert diagnostics["global"]["per_max"] == pytest.approx(10.0)
    assert diagnostics["global"]["peg_max"] == pytest.approx(1.0)


def test_rows_from_older_runs_are_scored_exactly_as_before():
    """Sans bloc `valuation`, on retombe sur per/peg : aucun run passé ne change."""
    rows = [_row(f"T{i}", "Technology", float(10 + i), 1.0 + i / 10.0) for i in range(25)]

    diagnostics = apply_sector_percentile_buy_signal(
        rows, percentile=0.50, min_sector_size=20, profiles_enabled=True
    )

    sector = diagnostics["sectors"]["Technologie"]
    assert sector["profile"] == "standard"
    assert sector["per_max"] == pytest.approx(22.0)


def test_stricter_percentile_accepts_fewer_names():
    rows = [_row(f"T{i}", "Technology", float(1 + i), 0.1 + i / 10.0) for i in range(25)]

    median = apply_sector_percentile_buy_signal(
        list(rows), percentile=0.50, min_sector_size=20
    )
    stricter = apply_sector_percentile_buy_signal(
        [_row(f"T{i}", "Technology", float(1 + i), 0.1 + i / 10.0) for i in range(25)],
        percentile=0.40, min_sector_size=20,
    )

    assert stricter["sectors"]["Technologie"]["per_max"] < median["sectors"]["Technologie"]["per_max"]
    assert stricter["accepted"] < median["accepted"]


def test_profiles_can_be_switched_off_globally():
    rows = [
        _row_with_valuation(
            f"REIT{i}", "Real Estate", {"p_ffo": 12.0, "peg_ffo": 1.0}, per=float(10 + i)
        )
        for i in range(25)
    ]

    diagnostics = apply_sector_percentile_buy_signal(
        rows, percentile=0.50, min_sector_size=20, profiles_enabled=False
    )

    assert diagnostics["sectors"]["Immobilier"]["profile"] == "standard"


def test_unknown_sector_always_uses_global_thresholds():
    rows = [
        _row(f"UNKNOWN{i}", "Unknown", float(i + 1), 0.1 + i / 100)
        for i in range(25)
    ] + [
        _row(f"TECH{i}", "Technology", float(100 + i), 2.0 + i / 100)
        for i in range(25)
    ]

    diagnostics = apply_sector_percentile_buy_signal(
        rows, percentile=0.40, min_sector_size=20
    )

    unknown = diagnostics["sectors"]["Inconnu"]
    assert unknown["source"] == "global"
    assert unknown["profile_fallback"] == "unknown_global"
    assert unknown["per_max"] == diagnostics["global"]["per_max"]
    assert unknown["peg_max"] == diagnostics["global"]["peg_max"]


def test_missing_quality_counts_distinguish_strict_acceptance_from_exclusion():
    rows = [
        _row(
            f"T{i}",
            "Technology",
            float(i + 1),
            None if i < 5 else 1.0,
        )
        for i in range(25)
    ]

    diagnostics = apply_sector_percentile_buy_signal(
        rows, percentile=0.40, min_sector_size=20
    )

    assert diagnostics["missing_quality_total"] == 5
    assert diagnostics["missing_quality_accepted"] == 5
    assert diagnostics["missing_quality_excluded"] == 0
    assert diagnostics["excluded_missing_peg"] == 0
