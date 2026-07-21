"""Déduplication des cross-listings.

ETF : par ISIN (identité exacte, colonne ToutBroker curée) puis, à défaut, par
nom normalisé EXACT. Deux lignes du même fonds (EIMI.L / EMIM.L) fusionnent ;
deux indices différents (noms/ISIN différents) restent séparés.
"""

import numpy as np
import pandas as pd
import pytest

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


# ── _ticker_currency : suffixe seul (aucun reseau) sauf .L, ou fast_info est
# lu par CLE (fast_info.get() est casse dans yfinance 1.x -> retournait
# toujours None, et l'appel HTTP throttle par ticker etait fait pour rien). ──

def test_ticker_currency_uses_suffix_without_network(monkeypatch):
    from app.services.finance.buffett import dedup

    def boom(*a, **k):
        raise AssertionError("appel yfinance interdit hors .L")

    monkeypatch.setattr("yfinance.Ticker", boom)
    assert dedup._ticker_currency("AIR.PA") == "EUR"
    assert dedup._ticker_currency("AAPL") == "USD"
    assert dedup._ticker_currency("7203.T") == "JPY"


def test_ticker_currency_dot_l_reads_fast_info_by_key(monkeypatch):
    from app.services.finance.buffett import dedup

    class _FI:
        def __getitem__(self, k):
            if k == "currency":
                return "GBp"
            raise KeyError(k)

        def get(self, _k, default=None):
            return default  # bug yfinance 1.x : .get() ignore la vraie valeur

    class _T:
        def __init__(self, *a, **k):
            self.fast_info = _FI()

    monkeypatch.setattr("yfinance.Ticker", _T)
    assert dedup._ticker_currency("SGLN.L") == "GBP"  # pence -> GBP


def test_ticker_currency_dot_l_falls_back_to_suffix_on_error(monkeypatch):
    from app.services.finance.buffett import dedup

    def boom(*a, **k):
        raise RuntimeError("reseau coupe")

    monkeypatch.setattr("yfinance.Ticker", boom)
    assert dedup._ticker_currency("HSBA.L") == "GBP"


# ── Dedup correlation ENTRE ETF seulement (decision utilisateur 2026-07-13) :
# une ACTION n'est jamais retiree pour cause de correlation, ni fusionnee avec
# un ETF (#bug : sur fenetre courte, KIE (ETF) etait absorbe par l'action ADBE,
# NOBL par NVO...). ──

def _perfect_twins(n=300):
    rng = np.random.RandomState(7)
    base = rng.randn(n)
    return base, base + 1e-9 * rng.randn(n)


def test_drop_correlated_ignores_stock_etf_pairs():
    from app.services.finance.buffett.dedup import drop_correlated
    a, b = _perfect_twins()
    rets = pd.DataFrame({"KIE": a, "ADBE": b})   # ETF vs ACTION, corr ~1
    kept, removed = drop_correlated(rets, {"KIE": 1, "ADBE": 999},
                                    threshold=0.95, removable={"KIE"})
    assert removed == []                          # paire ignoree : pas 2 ETF
    assert set(kept) == {"KIE", "ADBE"}


def test_drop_correlated_ignores_stock_stock_pairs():
    from app.services.finance.buffett.dedup import drop_correlated
    a, b = _perfect_twins()
    rets = pd.DataFrame({"TTE": a, "SHEL": b})   # deux ACTIONS correlees
    kept, removed = drop_correlated(rets, {"TTE": 1, "SHEL": 2},
                                    threshold=0.95, removable=set())
    assert removed == [] and set(kept) == {"TTE", "SHEL"}


def test_drop_correlated_still_merges_etf_etf_pairs():
    from app.services.finance.buffett.dedup import drop_correlated
    a, b = _perfect_twins()
    rets = pd.DataFrame({"IAU": a, "GLD": b})
    kept, removed = drop_correlated(rets, {"IAU": 10, "GLD": 999},
                                    threshold=0.95, removable={"IAU", "GLD"})
    assert [r[0] for r in removed] == ["IAU"]     # ETF-ETF : fusion normale
    assert kept == ["GLD"]


def test_deduplicate_correlated_protects_stocks_via_secteur():
    """deduplicate_correlated derive l'ensemble ETF de la colonne Secteur."""
    from app.services.finance.buffett.dedup import deduplicate_correlated
    a, b = _perfect_twins()
    rets = pd.DataFrame({"SPY": a, "AAPL": b})
    df = pd.DataFrame({
        _TCOL: ["SPY", "AAPL"],
        "Volume": [999, 1],
        "Secteur": ["ETF", "Technology"],
    })
    out = deduplicate_correlated(rets, df, _TCOL, threshold=0.95)
    assert set(out.columns) == {"SPY", "AAPL"}    # l'action n'est pas absorbee


# ── broker_access : ne pas retirer un jumeau qui est le SEUL représentant
# d'un broker actif -> sinon ce broker perd toute exposition à l'indice
# (bug rapporté : trop d'ETF retirés car la dispo broker n'était vérifiée
# qu'APRÈS le dédoublonnage corrélation, qui ne connaît que le volume). ──

def test_drop_correlated_keeps_pair_when_brokers_are_exclusive_and_disjoint():
    from app.services.finance.buffett.dedup import drop_correlated
    a, b = _perfect_twins()
    # A dispo seulement chez X (petit volume) ; B dispo seulement chez Y (gros
    # volume). Sans connaissance broker, l'ancien code retirait A (volume plus
    # faible) -> le broker X perdait toute exposition à cet indice.
    rets = pd.DataFrame({"A": a, "B": b})
    kept, removed = drop_correlated(
        rets, {"A": 1, "B": 999}, threshold=0.95,
        broker_access={"A": frozenset({"X"}), "B": frozenset({"Y"})},
    )
    assert removed == []
    assert set(kept) == {"A", "B"}


def test_drop_correlated_drops_subset_broker_access_even_low_volume_partner():
    from app.services.finance.buffett.dedup import drop_correlated
    a, b = _perfect_twins()
    # A dispo chez X et Y ; B dispo seulement chez Y (sous-ensemble de A) ->
    # retirer B ne fait perdre aucune exposition broker (A couvre déjà Y).
    rets = pd.DataFrame({"A": a, "B": b})
    kept, removed = drop_correlated(
        rets, {"A": 1, "B": 999}, threshold=0.95,
        broker_access={"A": frozenset({"X", "Y"}), "B": frozenset({"Y"})},
    )
    assert [r[0] for r in removed] == ["B"]
    assert kept == ["A"]


def test_drop_correlated_uses_volume_when_broker_access_identical():
    from app.services.finance.buffett.dedup import drop_correlated
    a, b = _perfect_twins()
    rets = pd.DataFrame({"A": a, "B": b})
    kept, removed = drop_correlated(
        rets, {"A": 1, "B": 999}, threshold=0.95,
        broker_access={"A": frozenset({"X"}), "B": frozenset({"X"})},
    )
    assert [r[0] for r in removed] == ["A"]   # même dispo -> volume tranche
    assert kept == ["B"]


def test_deduplicate_correlated_wires_broker_columns_from_df(monkeypatch):
    """deduplicate_correlated derive broker_access des colonnes fusionnees par
    merge_broker_columns (nommees exactement comme Config.BUDGET_BROKERS)."""
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.dedup import deduplicate_correlated
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"X": 1000.0, "Y": 1000.0})
    a, b = _perfect_twins()
    rets = pd.DataFrame({"A": a, "B": b})
    df = pd.DataFrame({
        _TCOL: ["A", "B"], "Volume": [1, 999], "Secteur": ["ETF", "ETF"],
        "X": [True, False], "Y": [False, True],
    })
    out = deduplicate_correlated(rets, df, _TCOL, threshold=0.95)
    assert set(out.columns) == {"A", "B"}   # exclusifs et disjoints -> gardes


def test_drop_correlated_min_periods_guards_sparse_overlap():
    """Deux series qui ne se recouvrent presque pas ne doivent JAMAIS fusionner,
    meme si leur correlation sur 3 jours communs vaut ~1."""
    from app.services.finance.buffett.dedup import drop_correlated
    n = 300
    rng = np.random.RandomState(8)
    a = pd.Series(rng.randn(n))
    b = a.copy()
    a[150:] = np.nan     # A n'existe que sur la 1re moitie
    b[:147] = np.nan     # B que sur la fin -> 3 jours de chevauchement
    rets = pd.DataFrame({"A": a, "B": b})
    kept, removed = drop_correlated(rets, {"A": 1, "B": 2}, threshold=0.95,
                                    removable={"A", "B"}, min_periods=60)
    assert removed == [] and set(kept) == {"A", "B"}


# ── drop_short_history : un fonds recent ne doit pas tronquer la fenetre
# commune de rendements de tout l'univers. ──

def test_drop_short_history_removes_young_funds():
    from app.services.finance.buffett.allocation import drop_short_history
    rng = np.random.RandomState(9)
    n = 1250
    old = pd.Series(rng.randn(n).cumsum() + 100)
    young = pd.Series([np.nan] * (n - 40) + list(rng.randn(40).cumsum() + 50))
    cd = pd.DataFrame({"VIEUX": old, "JEUNE": young})
    out, dropped = drop_short_history(cd, min_days=252)
    assert dropped == ["JEUNE"]
    assert list(out.columns) == ["VIEUX"]
    # La fenetre commune reste complete apres pct_change().dropna()
    rets = out.ffill().pct_change().dropna()
    assert len(rets) >= n - 2


def test_drop_short_history_keeps_everything_when_all_old():
    from app.services.finance.buffett.allocation import drop_short_history
    cd = pd.DataFrame(np.random.RandomState(10).randn(300, 3) + 100,
                      columns=["A", "B", "C"])
    out, dropped = drop_short_history(cd, min_days=252)
    assert dropped == [] and list(out.columns) == ["A", "B", "C"]


def test_drop_short_history_empty_frame():
    from app.services.finance.buffett.allocation import drop_short_history
    out, dropped = drop_short_history(pd.DataFrame(), min_days=252)
    assert dropped == []


def test_returns_are_converted_to_eur_before_correlation_and_starr(monkeypatch):
    from app.services.finance import yf_session as yf_module
    from app.services.finance.buffett import dedup

    index = pd.date_range("2026-01-01", periods=2, freq="D")
    returns = pd.DataFrame({"USD_ASSET": [0.0, 0.10], "EUR_ASSET": [0.0, 0.05]}, index=index)
    monkeypatch.setattr(
        dedup,
        "_ticker_currency",
        lambda ticker: "USD" if ticker == "USD_ASSET" else "EUR",
    )
    monkeypatch.setattr(
        yf_module,
        "download_with_timeout",
        lambda **kwargs: pd.DataFrame({"Close": [0.80, 0.88]}, index=index),
    )
    monkeypatch.setattr(yf_module, "yf_session", lambda: None)

    converted = dedup.returns_in_base_currency(returns, "EUR")

    assert converted.loc[index[1], "USD_ASSET"] == pytest.approx(0.21)
    assert converted.loc[index[1], "EUR_ASSET"] == pytest.approx(0.05)


def test_strict_eur_conversion_never_silently_uses_native_returns(monkeypatch):
    from app.services.finance import yf_session as yf_module
    from app.services.finance.buffett import dedup

    returns = pd.DataFrame({"USD_ASSET": [0.0, 0.1]})
    monkeypatch.setattr(dedup, "_ticker_currency", lambda _ticker: "USD")
    monkeypatch.setattr(yf_module, "download_with_timeout", lambda **kwargs: pd.DataFrame())
    monkeypatch.setattr(yf_module, "yf_session", lambda: None)

    with pytest.raises(RuntimeError, match="Conversion historique obligatoire"):
        dedup.returns_in_base_currency(returns, "EUR", strict=True)


def test_common_usd_eur_factor_increases_eur_correlation(monkeypatch):
    from app.services.finance import yf_session as yf_module
    from app.services.finance.buffett import dedup

    rng = np.random.default_rng(44)
    index = pd.date_range("2024-01-01", periods=500, freq="D")
    native = pd.DataFrame(
        {"USD_A": rng.normal(0, 0.005, 500), "USD_B": rng.normal(0, 0.005, 500)},
        index=index,
    )
    fx_returns = rng.normal(0, 0.012, 500)
    fx_close = 0.9 * np.cumprod(1.0 + fx_returns)
    monkeypatch.setattr(dedup, "_ticker_currency", lambda _ticker: "USD")
    monkeypatch.setattr(
        yf_module,
        "download_with_timeout",
        lambda **kwargs: pd.DataFrame({"Close": fx_close}, index=index),
    )
    monkeypatch.setattr(yf_module, "yf_session", lambda: None)

    converted = dedup.returns_in_base_currency(native, "EUR", strict=True)

    assert converted.corr().iloc[0, 1] > native.corr().iloc[0, 1] + 0.5
