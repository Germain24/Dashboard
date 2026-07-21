"""Analyse financière Buffett — wrapper pandas autour de scoring_pure."""

from __future__ import annotations

import math

from .cache_manager import infer_country
from .config import Config
from .scoring_pure import (
    compute_buy_signal,
    compute_moat_score,
    compute_score_coverage,
    robust_growth,
    select_growth,
)


def _v(s, i):
    """Valeur scalaire sécurisée depuis Series ou scalaire."""
    try:
        value = float(s.iloc[i]) if hasattr(s, "iloc") else float(s)
        return value if math.isfinite(value) else None
    except Exception:
        return None


def _b(s, i, growth=False):
    """Valeur booléenne (croissance ou signe), None si donnée absente."""
    try:
        value = s.diff().iloc[i] if growth and hasattr(s, "diff") else s.iloc[i]
        value = float(value)
        return bool(value > 0) if math.isfinite(value) else None
    except Exception:
        return None


def _safe(func, n=1, index=None):
    """Série numérique sans inventer de zéro pour une donnée absente."""
    import numpy as np
    import pandas as pd

    try:
        r = func()
        if isinstance(r, (pd.Series, pd.DataFrame)):
            r = pd.to_numeric(r, errors="coerce")
            return r.replace([np.inf, -np.inf], np.nan)
        value = pd.to_numeric(r, errors="coerce")
        return pd.Series([value] * n, index=index, dtype=float).replace(
            [np.inf, -np.inf], np.nan
        )
    except Exception:
        return pd.Series([float("nan")] * n, index=index, dtype=float)


def extract_metrics(symbol: str, info: dict) -> dict:
    if not info:
        info = {}
    qt = info.get("quoteType", "").upper()
    ln, sn = info.get("longName", ""), info.get("shortName", "")
    # NB : la classification ETF est décidée par etf_detect.is_etf (financials +
    # nom de fonds), pas ici sur le seul quoteType/nom — sinon les cotations
    # secondaires (quoteType="ETF" à tort) écrasent le vrai secteur.
    secteur = info.get("sector", "Inconnu")
    pays = info.get("country", "Inconnu")
    if pays == "Inconnu":
        pays = infer_country(symbol)
    prix = info.get("currentPrice", info.get("regularMarketPrice", 0))
    from .currency import volume_eur
    return {
        "Nom": ln or sn or symbol, "Pays": pays,
        "Prix": prix,
        "EPS": info.get("trailingEps", 0), "PER": info.get("trailingPE", 0),
        # Volume échangé/jour EN EUROS (nb actions x prix local x FX), pas le
        # nombre brut d'actions -- cf. currency.volume_eur.
        "Volume": volume_eur(
            info.get("volume", info.get("regularMarketVolume", 0)), prix, symbol, info,
        ),
        # Marqueur d'unité : permet au cache chaud de distinguer ces métriques
        # des historiques en nb d'actions (cf. currency.ensure_volume_eur).
        "VolumeDevise": "EUR",
        "Secteur": secteur, "Industrie": info.get("industry", "Inconnu"),
        "QuoteType": qt,
    }


def _norm_date_index(df):
    """Normalise l'index (dates) en chaînes 'YYYY-MM-DD' quel que soit le dtype source.

    Corrige le bug "None of [DatetimeIndex(...)] are in the [index]" : selon que les
    données viennent de yfinance (DatetimeIndex / datetime64[s] / Timestamps en objet /
    tz-aware) ou du cache Excel (chaînes), les index des 3 états financiers pouvaient
    avoir des dtypes incohérents, faisant échouer l'intersection puis le .loc, ou la
    rendant silencieusement vide. On ramène tout à une représentation canonique unique.
    """
    import pandas as pd
    if df is None or getattr(df, "empty", True):
        return df
    df = df.copy()
    parsed = pd.to_datetime(df.index, errors="coerce", utc=True)
    new_idx = [
        p.strftime("%Y-%m-%d") if pd.notna(p) else str(o)
        for o, p in zip(df.index, parsed)
    ]
    df.index = new_idx
    # Dédupe d'éventuelles dates répétées (merge cache + yfinance)
    df = df[~df.index.duplicated(keep="first")]
    return df


def _filter_incomplete(df):
    """Filtre les lignes (dates) à >50% de valeurs manquantes puis normalise l'index."""
    import pandas as pd
    num = df.select_dtypes(include=["number"]).columns
    f = df[df[num].isnull().mean(axis=1) < 0.5] if len(num) else df
    return _norm_date_index(f)


def analyze_financials(symbol: str, data: dict, etf_tickers: set | None = None) -> tuple[float, dict]:
    """Analyse financière complète → (score 0-100, metrics dict).

    ``etf_tickers`` : ensemble AUTORITAIRE des tickers ETF (ToutBroker 'Secteur 1'
    == 'ETF'). Si None, chargé depuis ToutBroker. Un ticker ETF → Score=200.
    """
    import pandas as pd

    if etf_tickers is None:
        from .broker_availability import load_etf_tickers
        etf_tickers = load_etf_tickers()

    info = data.get("info", {})
    metrics = extract_metrics(symbol, info)
    is_etf = symbol.upper() in etf_tickers
    is_forced = symbol.upper() in [t.upper() for t in Config.FORCED_BUY_TICKERS]
    if is_forced or is_etf:
        metrics["Achat"] = True
        if is_etf: metrics["Secteur"] = "ETF"
        return 200.0, metrics  # ETF/forcé : score conventionnel = 200

    income, balance, cashflow = data.get("income"), data.get("balance"), data.get("cashflow")
    if income is None or income.empty or balance is None or balance.empty:
        return 0.0, metrics

    # Normaliser les index en chaînes 'YYYY-MM-DD' (cf. _norm_date_index), puis réintersecter
    income   = _filter_incomplete(income.sort_index())
    balance  = _filter_incomplete(balance.sort_index())
    cashflow = _filter_incomplete(cashflow.sort_index()) if cashflow is not None and not cashflow.empty else pd.DataFrame()
    common = income.index.intersection(balance.index)
    if not cashflow.empty:
        common = common.intersection(cashflow.index)
    if common.empty: return 0.0, metrics
    # Ordre préservé identique à l'origine (intersection triée ascendante par défaut)
    income   = income.loc[common]
    balance  = balance.loc[common]
    cashflow = cashflow.loc[common] if not cashflow.empty else cashflow
    for df_ in [income, balance, cashflow]:
        for col in df_.columns:
            # Conserver les NaN : zéro est une vraie valeur financière, pas un
            # synonyme de « Yahoo n'a pas fourni ce poste ».
            df_[col] = pd.to_numeric(df_[col], errors="coerce")

    n = len(income)
    idx = income.index

    def _col(df, *names):
        for name in names:
            if name in df.columns:
                return df[name]
        raise KeyError(names[0])

    gpm = _safe(
        lambda: income["Gross Profit"].abs() / income["Total Revenue"].abs(), n, idx
    )
    sga = _safe(
        lambda: income["Selling General And Administration"].abs()
        / income["Gross Profit"].abs(), n, idx
    )
    rd = _safe(
        lambda: income["Research And Development"].abs() / income["Gross Profit"].abs(),
        n, idx,
    )
    dep = _safe(
        lambda: income["Reconciled Depreciation"].abs() / income["Gross Profit"].abs(),
        n, idx,
    )
    inx = _safe(
        lambda: income["Interest Expense"].abs() / income["Operating Income"].abs(),
        n, idx,
    )
    pt = _safe(lambda: income["Pretax Income"], n, idx)
    ni = _safe(lambda: income["Net Income"], n, idx)
    nim = _safe(lambda: income["Net Income"] / income["Total Revenue"].abs(), n, idx)
    eps_ = _safe(
        lambda: income["Net Income"] / balance["Ordinary Shares Number"], n, idx
    )
    cash_columns = [
        c for c in [
            "Cash Cash Equivalents And Short Term Investments",
            "Inventory",
            "Accounts Receivable",
        ]
        if c in balance.columns
    ]
    cash = (
        balance[cash_columns].sum(axis=1, min_count=1)
        if cash_columns
        else pd.Series(float("nan"), index=idx)
    )

    def _roic():
        tax_rate = (income["Tax Provision"] / income["Pretax Income"]).clip(0.0, 0.35)
        nopat = income["Operating Income"] * (1.0 - tax_rate)
        invested = _col(balance, "Invested Capital")
        return nopat / invested.abs()

    total_debt = _safe(
        lambda: _col(balance, "Total Debt", "Net Debt"), n, idx
    )
    long_term_debt = _safe(
        lambda: _col(
            balance,
            "Long Term Debt And Capital Lease Obligation",
            "Long Term Debt",
        ),
        n,
        idx,
    )
    roic = _safe(_roic, n, idx)
    dr = _safe(lambda: total_debt / balance["Total Assets"].abs(), n, idx)
    lr = _safe(lambda: balance["Current Assets"] / balance["Current Liabilities"], n, idx)
    ltd = _safe(lambda: long_term_debt / income["Pretax Income"].abs(), n, idx)
    deq = _safe(
        lambda: total_debt / _col(balance, "Stockholders Equity", "Common Stock Equity").abs(),
        n,
        idx,
    )
    ret = _safe(lambda: balance["Retained Earnings"], n, idx)
    cv = _safe(
        lambda: cashflow["Issuance Of Capital Stock"]
        + cashflow["Repurchase Of Capital Stock"],
        n,
        idx,
    )
    roe_ = _safe(
        lambda: income["Net Income"]
        / _col(balance, "Stockholders Equity", "Common Stock Equity").abs(),
        n,
        idx,
    )
    cpx = _safe(
        lambda: cashflow["Capital Expenditure"].abs() / income["Net Income"].abs(),
        n,
        idx,
    )
    bb = _safe(lambda: -cashflow["Repurchase Of Capital Stock"], n, idx)

    def _truth(value, predicate):
        return None if value is None else bool(predicate(value))

    yearly = [{"gpm":_v(gpm,i),"sga":_v(sga,i),"rd":_v(rd,i),"depr":_v(dep,i),"interest_exp":_v(inx,i),
               "pretax_growth":_b(pt,i,True),"net_income_growth":_b(ni,i,True),"net_income_positive":_b(ni,i),
               "nim":_v(nim,i),"eps_growth":_b(eps_,i,True),"cash_growth":_b(cash,i,True),
               "debt_ratio":_v(dr,i),"liab_ratio":_v(lr,i),"lt_debt_ratio":_v(ltd,i),"debt_eq":_v(deq,i),
               "retained_growth":_b(ret,i,True),"cap_stock_var":_truth(_v(cv,i), lambda v: v < 0),"roe":_v(roe_,i),
               "roic":_v(roic,i),"capex":_v(cpx,i),"buybacks":_truth(_v(bb,i), lambda v: v > 0)} for i in range(n)]

    secteur = str(metrics.get("Secteur") or "")
    industrie = str(metrics.get("Industrie") or "")
    score = compute_moat_score(yearly, secteur, industrie)
    metrics["score_coverage_pct"] = compute_score_coverage(yearly, secteur, industrie)
    # Les séries sont triées ancien → récent : la dernière ligne est la plus récente.
    if yearly:
        metrics["ratios_recents"] = yearly[-1]
    growth = growth_rev = growth_eps = forward = None
    growth_reliable = True
    try:
        for lbl in ("Total Revenue","Revenue"):
            if lbl in income.columns:
                growth_rev = robust_growth(list(income[lbl].dropna().values))
                break
        ev = [float(e) for e in (eps_.values if hasattr(eps_,"values") else [eps_])]
        growth_eps = robust_growth(ev)
        # Croissance FUTURE prévue (analystes) : EPS forward vs EPS trailing (info).
        fwd_eps = float(info.get("forwardEps") or 0)
        trail_eps = float(metrics.get("EPS") or 0)
        forward = (fwd_eps / trail_eps - 1.0) if (fwd_eps and trail_eps > 0) else None
        growth, growth_reliable = select_growth(forward, growth_rev, growth_eps)
    except Exception: pass

    metrics.update({"CAGR":growth,"CAGR_Rev":growth_rev,"CAGR_EPS":growth_eps,
                    "CAGR_Forward":forward,"growth_reliable":growth_reliable})
    achat, peg = compute_buy_signal(
        metrics.get("Secteur","Inconnu"), metrics.get("Pays","Inconnu"),
        float(metrics.get("Prix") or 0), float(metrics.get("EPS") or 0),
        float(metrics.get("PER") or 0), growth,
        Config.TAUX_OBLIGATAIRES, Config.TAUX_DEFAUT, Config.PER_MAX, Config.PEG_MAX,
        growth_reliable=growth_reliable,
    )
    metrics["Achat"] = achat
    metrics["PEG"] = peg
    return score, metrics
