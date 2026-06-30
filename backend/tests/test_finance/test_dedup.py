"""Déduplication des cross-listings.

ETF : par ISIN (identité exacte, colonne ToutBroker curée) puis, à défaut, par
nom normalisé EXACT. Deux lignes du même fonds (EIMI.L / EMIM.L) fusionnent ;
deux indices différents (noms/ISIN différents) restent séparés.
"""

import numpy as np
import pandas as pd

from app.services.finance.buffett.dedup import deduplicate_tickers

_TCOL = "Ticker Yahoo Finance"


def _setup(rows):
    tickers = [r["Ticker"] for r in rows]
    returns = pd.DataFrame(
        np.random.RandomState(0).randn(20, len(tickers)), columns=tickers
    )
    df = pd.DataFrame(rows).rename(columns={"Ticker": _TCOL})
    return returns, df


_EM_NAME = "iShares Core MSCI EM IMI UCITS ETF USD (Acc)"


def test_etf_same_isin_merged():
    returns, df = _setup([
        {"Ticker": "EIMI.L", "Nom": _EM_NAME, "Volume": 1000, "Secteur": "ETF", "ISIN": "IE00BKM4GZ66"},
        {"Ticker": "EMIM.L", "Nom": _EM_NAME, "Volume": 500, "Secteur": "ETF", "ISIN": "IE00BKM4GZ66"},
    ])
    out = deduplicate_tickers(returns, df)
    assert list(out.columns) == ["EIMI.L"]  # garde la ligne la plus liquide


def test_etf_identical_name_merged_without_isin():
    returns, df = _setup([
        {"Ticker": "EIMI.L", "Nom": _EM_NAME, "Volume": 1000, "Secteur": "ETF", "ISIN": None},
        {"Ticker": "EMIM.L", "Nom": _EM_NAME, "Volume": 500, "Secteur": "ETF", "ISIN": None},
    ])
    out = deduplicate_tickers(returns, df)
    assert list(out.columns) == ["EIMI.L"]


def test_etf_dedup_without_isin_column_at_all():
    # df ne contient AUCUNE colonne ISIN -> repli nom exact, pas de crash.
    returns, df = _setup([
        {"Ticker": "EIMI.L", "Nom": _EM_NAME, "Volume": 1000, "Secteur": "ETF"},
        {"Ticker": "EMIM.L", "Nom": _EM_NAME, "Volume": 500, "Secteur": "ETF"},
    ])
    out = deduplicate_tickers(returns, df)
    assert list(out.columns) == ["EIMI.L"]


def test_etf_different_isin_kept_even_if_same_name():
    # Acc vs Dist : même nom, ISIN différents -> 2 fonds distincts.
    returns, df = _setup([
        {"Ticker": "A.L", "Nom": _EM_NAME, "Volume": 1000, "Secteur": "ETF", "ISIN": "IE00BKM4GZ66"},
        {"Ticker": "B.L", "Nom": _EM_NAME, "Volume": 500, "Secteur": "ETF", "ISIN": "IE00B0M63177"},
    ])
    out = deduplicate_tickers(returns, df)
    assert set(out.columns) == {"A.L", "B.L"}


def test_etf_different_names_kept():
    returns, df = _setup([
        {"Ticker": "WLD.L", "Nom": "iShares Core MSCI World UCITS ETF", "Volume": 1000, "Secteur": "ETF", "ISIN": None},
        {"Ticker": "EM.L", "Nom": "iShares Core MSCI Emerging Markets UCITS ETF", "Volume": 500, "Secteur": "ETF", "ISIN": None},
    ])
    out = deduplicate_tickers(returns, df)
    assert set(out.columns) == {"WLD.L", "EM.L"}


def test_etf_blank_isin_falls_back_to_name():
    # ISIN vide / '-' (sentinelle yfinance "introuvable") -> repli nom exact.
    returns, df = _setup([
        {"Ticker": "EIMI.L", "Nom": _EM_NAME, "Volume": 1000, "Secteur": "ETF", "ISIN": "-"},
        {"Ticker": "EMIM.L", "Nom": _EM_NAME, "Volume": 500, "Secteur": "ETF", "ISIN": "  "},
    ])
    out = deduplicate_tickers(returns, df)
    assert list(out.columns) == ["EIMI.L"]


def test_drop_correlated_removes_lower_volume_twin():
    from app.services.finance.buffett.dedup import drop_correlated
    rng = np.random.RandomState(1)
    base = rng.randn(200)
    rets = pd.DataFrame({
        "A": base, "B": base + 1e-9 * rng.randn(200),  # ~parfaitement corrélés
        "C": rng.randn(200),                            # indépendant
    })
    kept, removed = drop_correlated(rets, {"A": 100, "B": 50, "C": 80}, threshold=0.97)
    assert [r[0] for r in removed] == ["B"]   # plus faible volume du couple A/B
    assert removed[0][1] == "A"               # partenaire gardé
    assert removed[0][2] >= 0.97              # corrélation loggée
    assert set(kept) == {"A", "C"}


def test_drop_correlated_keeps_distinct_exposures():
    from app.services.finance.buffett.dedup import drop_correlated
    rng = np.random.RandomState(2)
    rets = pd.DataFrame({"A": rng.randn(200), "B": rng.randn(200)})
    kept, removed = drop_correlated(rets, {"A": 1, "B": 2}, threshold=0.97)
    assert removed == [] and set(kept) == {"A", "B"}


def _removed_tickers(removed):
    return [r[0] for r in removed]


def test_drop_correlated_below_threshold_kept():
    from app.services.finance.buffett.dedup import drop_correlated
    rng = np.random.RandomState(3)
    a = rng.randn(500)
    b = a + 0.9 * rng.randn(500)          # corrélés mais < 0.97
    rets = pd.DataFrame({"A": a, "B": b})
    assert rets.corr().loc["A", "B"] < 0.97
    kept, removed = drop_correlated(rets, {"A": 1, "B": 1}, threshold=0.97)
    assert removed == []


def test_drop_correlated_chain_keeps_highest_volume():
    from app.services.finance.buffett.dedup import drop_correlated
    rng = np.random.RandomState(4)
    base = rng.randn(300)
    rets = pd.DataFrame({"A": base, "B": base.copy(), "C": base.copy()})
    kept, removed = drop_correlated(rets, {"A": 10, "B": 99, "C": 50}, threshold=0.97)
    assert kept == ["B"]                   # garde le plus liquide du triplet
    assert set(_removed_tickers(removed)) == {"A", "C"}


def test_stock_cross_listing_still_merged_by_name():
    # Régression : les ACTIONS continuent d'être dédupliquées par nom flou.
    returns, df = _setup([
        {"Ticker": "NVO", "Nom": "Novo Nordisk A/S", "Volume": 1000, "Secteur": "Healthcare", "ISIN": None},
        {"Ticker": "NOVO-B.CO", "Nom": "Novo Nordisk A/S", "Volume": 500, "Secteur": "Healthcare", "ISIN": None},
    ])
    out = deduplicate_tickers(returns, df)
    assert list(out.columns) == ["NVO"]
