"""Concentration économique : look-through prudent des ETF actions larges."""

from __future__ import annotations

from app.services.finance.risk import (
    _load_diversified_tickers,
    compute_portfolio_hhi,
    get_risk_metrics,
)

SNAPSHOTS = [
    {"date": "2026-01-01", "valeur": 100.0, "investit": 100.0},
    {"date": "2026-01-02", "valeur": 101.0, "investit": 100.0},
    {"date": "2026-01-03", "valeur": 100.5, "investit": 100.0},
]


def test_world_etf_dominant_portfolio_is_diversified_lookthrough():
    positions = [
        {"ticker": "CW8.PA", "valeur_actuelle": 9_000.0},
        {"ticker": "SGLN.L", "valeur_actuelle": 1_000.0},
    ]

    metrics = get_risk_metrics(
        SNAPSHOTS,
        positions,
        diversified_tickers={"CW8.PA"},
    )

    assert metrics["hhi"] < 0.10
    assert metrics["concentration"] == "faible"


def test_single_stock_dominant_portfolio_remains_highly_concentrated():
    positions = [
        {"ticker": "AAPL", "valeur_actuelle": 9_000.0},
        {"ticker": "SGLN.L", "valeur_actuelle": 1_000.0},
    ]

    metrics = get_risk_metrics(
        SNAPSHOTS,
        positions,
        diversified_tickers=set(),
    )

    assert metrics["hhi"] == 0.82
    assert metrics["concentration"] == "élevée"


def test_same_ticker_across_brokers_is_aggregated_before_hhi():
    positions = [
        {"ticker": "AAPL", "broker": "one", "valeur_actuelle": 4_000.0},
        {"ticker": "AAPL", "broker": "two", "valeur_actuelle": 5_000.0},
        {"ticker": "MSFT", "valeur_actuelle": 1_000.0},
    ]

    assert compute_portfolio_hhi(positions, diversified_tickers=set()) == 0.82


def test_automatic_lookthrough_only_whitelists_broad_multi_country_equity_etfs(
    monkeypatch,
):
    from app.services.finance.buffett import breakdown, lookthrough

    monkeypatch.setattr(
        breakdown,
        "load_classification",
        lambda: (
            {
                "CW8.PA": "Actions",
                "ARKK": "Actions",
                "BITO": "Actions",
                "XLK": "Actions",
                "BOND": "Obligations",
            },
            {
                "CW8.PA": "Actions diversifiées",
                "ARKK": "Actions diversifiées",
                "BITO": "Actions diversifiées",
                "XLK": "Technologie",
                "BOND": "Actions diversifiées",
            },
        ),
    )
    monkeypatch.setattr(
        lookthrough,
        "load_lookthrough",
        lambda: (
            {},
            {
                "CW8.PA": {"United States": 0.70, "Japan": 0.06},
                "ARKK": {"United States": 1.0},
                "BITO": {},
                "XLK": {"United States": 1.0},
                "BOND": {"United States": 0.60, "France": 0.40},
            },
        ),
    )
    _load_diversified_tickers.cache_clear()

    assert _load_diversified_tickers() == frozenset({"CW8.PA"})

    _load_diversified_tickers.cache_clear()
