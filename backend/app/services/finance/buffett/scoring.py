"""Analyse financière Buffett — wrapper pandas autour de scoring_pure."""

from __future__ import annotations

import math

from .breakdown import _canon_sector
from .cache_manager import infer_country
from .config import Config
from .scoring_pure import (
    compute_buffett_score_v3,
    compute_comparable_peg,
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


def _growth_rate(s, i):
    """Croissance YoY numérique, sans inventer de taux sur une base négative."""
    if i <= 0:
        return None
    try:
        current = float(s.iloc[i])
        previous = float(s.iloc[i - 1])
        if not math.isfinite(current) or not math.isfinite(previous) or previous <= 0:
            return None
        return current / previous - 1.0
    except Exception:
        return None


def _metric_state(value, *, economically_invalid: bool = False) -> str:
    """État explicite d'une mesure, distinct de sa valeur numérique."""
    if economically_invalid:
        return "ECONOMICALLY_INVALID"
    try:
        return "VALID" if math.isfinite(float(value)) else "MISSING"
    except (TypeError, ValueError):
        return "MISSING"


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
    entity_overrides = {
        "HEMNF": {
            "sector": "Communication Services",
            "industry": "Internet Content & Information",
            "country": "Sweden",
        },
    }
    override = entity_overrides.get(str(symbol).strip().upper(), {})
    if str(secteur or "").strip().casefold() in {"", "inconnu", "unknown"}:
        secteur = override.get("sector", secteur)
    if str(pays or "").strip().casefold() in {"", "inconnu", "unknown"}:
        pays = override.get("country", pays)
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
        "Secteur": secteur,
        "Industrie": info.get("industry") or override.get("industry") or "Inconnu",
        "QuoteType": qt,
        # Métriques de valorisation sectorielle. Toutes déjà présentes dans le
        # `.info` mis en cache : aucun appel réseau supplémentaire.
        "DividendYield": info.get("dividendYield"),
        "PriceToBook": info.get("priceToBook"),
        "ROE": info.get("returnOnEquity"),
        "MarketCap": info.get("marketCap"),
        "BookValue": info.get("bookValue"),
    }


def _valuation_fundamentals(income, balance, cashflow) -> dict:
    """Postes comptables bruts nécessaires au FFO et au PER normalisé.

    Isole ici tout ce qui touche à pandas : ``sector_valuation`` reste pur Python
    et donc testable sans DataFrame, comme ``scoring_pure``.
    """

    def _last(df, *names):
        if df is None or getattr(df, "empty", True):
            return None
        for name in names:
            if name in df.columns:
                series = df[name].dropna()
                if not series.empty:
                    return float(series.iloc[-1])
        return None

    def _series(df, *names):
        if df is None or getattr(df, "empty", True):
            return []
        for name in names:
            if name in df.columns:
                return [float(value) for value in df[name].dropna().tolist()]
        return []

    return {
        "net_income": _last(income, "Net Income", "Net Income Common Stockholders"),
        "net_income_series": _series(
            income, "Net Income", "Net Income Common Stockholders"
        ),
        "depreciation_amortization": (
            _last(cashflow, "Depreciation And Amortization")
            or _last(income, "Reconciled Depreciation", "Depreciation And Amortization")
        ),
        "gain_loss_on_sale_ppe": _last(cashflow, "Gain Loss On Sale Of PPE"),
        "shares_outstanding": _last(balance, "Ordinary Shares Number", "Share Issued"),
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
    num = df.select_dtypes(include=["number"]).columns
    f = df[df[num].isnull().mean(axis=1) < 0.5] if len(num) else df
    return _norm_date_index(f)


def analyze_financials(symbol: str, data: dict, etf_tickers: set | None = None) -> tuple[float, dict]:
    """Analyse financière complète → (score 0-100, metrics dict).

    ``etf_tickers`` : ensemble AUTORITAIRE des tickers ETF (ToutBroker 'Secteur 1'
    == 'ETF'). Si None, chargé depuis le catalogue. Le MOAT d'un ETF est N/A.
    """
    import pandas as pd

    if etf_tickers is None:
        from .broker_availability import load_etf_tickers
        etf_tickers = load_etf_tickers()

    info = data.get("info", {})
    metrics = extract_metrics(symbol, info)
    is_etf = symbol.upper() in etf_tickers
    if is_etf:
        metrics["Achat"] = True
        metrics["Secteur"] = "ETF"
        metrics["InstrumentType"] = "ETF"
        return 0.0, metrics

    income, balance, cashflow = data.get("income"), data.get("balance"), data.get("cashflow")
    if income is None or income.empty or balance is None or balance.empty:
        return 0.0, metrics

    # Normaliser les index en chaînes 'YYYY-MM-DD' (cf. _norm_date_index), puis réintersecter
    income   = _filter_incomplete(income.sort_index())
    balance  = _filter_incomplete(balance.sort_index())
    cashflow = _filter_incomplete(cashflow.sort_index()) if cashflow is not None and not cashflow.empty else pd.DataFrame()
    # Union des exercices : l'absence du cash-flow d'une année ne doit pas faire
    # perdre les marges, le bilan et la rentabilité pourtant disponibles.
    common = income.index.union(balance.index)
    if not cashflow.empty:
        common = common.union(cashflow.index)
    common = common.sort_values()
    if common.empty: return 0.0, metrics
    income = income.reindex(common)
    balance = balance.reindex(common)
    cashflow = cashflow.reindex(common) if not cashflow.empty else pd.DataFrame(index=common)
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

    revenue = _safe(lambda: _col(income, "Total Revenue", "Revenue"), n, idx)
    gross_profit = _safe(lambda: income["Gross Profit"], n, idx)
    equity = _safe(
        lambda: _col(balance, "Stockholders Equity", "Common Stock Equity"), n, idx
    )
    invested_capital = _safe(lambda: _col(balance, "Invested Capital"), n, idx)
    operating_income = _safe(lambda: income["Operating Income"], n, idx)

    gpm = _safe(lambda: gross_profit / revenue.where(revenue > 0), n, idx)
    sga = _safe(
        lambda: income["Selling General And Administration"].abs()
        / gross_profit.where(gross_profit > 0), n, idx
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
        lambda: income["Interest Expense"].abs() / operating_income.where(operating_income > 0),
        n, idx,
    )
    pt = _safe(lambda: income["Pretax Income"], n, idx)
    ni = _safe(lambda: income["Net Income"], n, idx)
    nim = _safe(lambda: income["Net Income"] / revenue.where(revenue > 0), n, idx)
    eps_ = _safe(
        lambda: income["Net Income"] / balance["Ordinary Shares Number"].where(
            balance["Ordinary Shares Number"] > 0
        ), n, idx
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
        return nopat / invested_capital.where(invested_capital > 0)

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
    total_assets = _safe(lambda: balance["Total Assets"], n, idx)
    current_liabilities = _safe(lambda: balance["Current Liabilities"], n, idx)
    dr = _safe(lambda: total_debt.clip(lower=0) / total_assets.where(total_assets > 0), n, idx)
    lr = _safe(lambda: balance["Current Assets"] / current_liabilities.where(current_liabilities > 0), n, idx)
    ltd = _safe(lambda: long_term_debt.clip(lower=0) / pt.where(pt > 0), n, idx)
    deq = _safe(lambda: total_debt.clip(lower=0) / equity.where(equity > 0), n, idx)
    ret = _safe(lambda: balance["Retained Earnings"], n, idx)
    cv = _safe(
        lambda: cashflow["Issuance Of Capital Stock"]
        + cashflow["Repurchase Of Capital Stock"],
        n,
        idx,
    )
    roe_ = _safe(lambda: income["Net Income"] / equity.where(equity > 0), n, idx)
    cpx = _safe(
        lambda: cashflow["Capital Expenditure"].abs() / ni.where(ni > 0),
        n,
        idx,
    )
    bb = _safe(lambda: -cashflow["Repurchase Of Capital Stock"], n, idx)
    shares = _safe(lambda: balance["Ordinary Shares Number"], n, idx)

    def _free_cash_flow():
        if "Free Cash Flow" in cashflow.columns:
            return cashflow["Free Cash Flow"]
        operating = _col(
            cashflow,
            "Operating Cash Flow",
            "Total Cash From Operating Activities",
        )
        capex_raw = _col(cashflow, "Capital Expenditure", "Capital Expenditures")
        return operating - capex_raw.abs()

    fcf = _safe(_free_cash_flow, n, idx)
    fcf_to_ni = _safe(lambda: fcf / ni.where(ni > 0), n, idx)
    fcf_margin = _safe(lambda: fcf / revenue.where(revenue > 0), n, idx)
    fcf_per_share = _safe(lambda: fcf / shares.where(shares > 0), n, idx)

    def _truth(value, predicate):
        return None if value is None else bool(predicate(value))

    yearly = [{"gpm":_v(gpm,i),"sga":_v(sga,i),"rd":_v(rd,i),"depr":_v(dep,i),"interest_exp":_v(inx,i),
               "pretax_growth":_b(pt,i,True),"net_income_growth":_b(ni,i,True),"net_income_positive":_b(ni,i),
               "nim":_v(nim,i),"eps_growth":_b(eps_,i,True),"cash_growth":_b(cash,i,True),
               "debt_ratio":_v(dr,i),"liab_ratio":_v(lr,i),"lt_debt_ratio":_v(ltd,i),"debt_eq":_v(deq,i),
               "retained_growth":_b(ret,i,True),"cap_stock_var":_truth(_v(cv,i), lambda v: v < 0),"roe":_v(roe_,i),
               "roic":_v(roic,i),"capex":_v(cpx,i),"buybacks":_truth(_v(bb,i), lambda v: v > 0),
               "pretax_growth_rate":_growth_rate(pt,i),"net_income_growth_rate":_growth_rate(ni,i),
               "eps_growth_rate":_growth_rate(eps_,i),"cash_growth_rate":_growth_rate(cash,i),
               "share_count_growth":_growth_rate(shares,i),"fcf_to_net_income":_v(fcf_to_ni,i),
               "fcf_margin":_v(fcf_margin,i),"fcf_per_share_growth_rate":_growth_rate(fcf_per_share,i),
               "operating_income_positive": _truth(_v(operating_income, i), lambda v: v > 0),
               "fcf_positive": _truth(_v(fcf, i), lambda v: v > 0),
               "pretax_income_positive": _truth(_v(pt, i), lambda v: v > 0),
               "equity_positive": _truth(_v(equity, i), lambda v: v > 0),
               "invested_capital_positive": _truth(_v(invested_capital, i), lambda v: v > 0),
               "metric_states": {
                   "gpm": _metric_state(_v(gpm, i), economically_invalid=(_v(revenue, i) is not None and _v(revenue, i) <= 0)),
                   "nim": _metric_state(_v(nim, i), economically_invalid=(_v(revenue, i) is not None and _v(revenue, i) <= 0)),
                   "sga": _metric_state(_v(sga, i), economically_invalid=(_v(gross_profit, i) is not None and _v(gross_profit, i) <= 0)),
                   "interest_exp": _metric_state(_v(inx, i), economically_invalid=(_v(operating_income, i) is not None and _v(operating_income, i) <= 0)),
                   "roe": _metric_state(_v(roe_, i), economically_invalid=(_v(equity, i) is not None and _v(equity, i) <= 0)),
                   "roic": _metric_state(_v(roic, i), economically_invalid=(_v(invested_capital, i) is not None and _v(invested_capital, i) <= 0)),
                   "debt_ratio": _metric_state(_v(dr, i), economically_invalid=(_v(total_assets, i) is not None and _v(total_assets, i) <= 0)),
                   "liab_ratio": _metric_state(_v(lr, i), economically_invalid=(_v(current_liabilities, i) is not None and _v(current_liabilities, i) <= 0)),
                   "lt_debt_ratio": _metric_state(_v(ltd, i), economically_invalid=(_v(pt, i) is not None and _v(pt, i) <= 0)),
                   "debt_eq": _metric_state(_v(deq, i), economically_invalid=(_v(equity, i) is not None and _v(equity, i) <= 0)),
                   "capex": _metric_state(_v(cpx, i), economically_invalid=(_v(ni, i) is not None and _v(ni, i) <= 0)),
                   "fcf_to_net_income": _metric_state(_v(fcf_to_ni, i), economically_invalid=(_v(ni, i) is not None and _v(ni, i) <= 0)),
                   "fcf_margin": _metric_state(_v(fcf_margin, i), economically_invalid=(_v(revenue, i) is not None and _v(revenue, i) <= 0)),
                   "share_count_growth": (
                       "NOT_APPLICABLE" if i == 0 else
                       _metric_state(_growth_rate(shares, i), economically_invalid=(_v(shares, i - 1) is not None and _v(shares, i - 1) <= 0))
                   ),
                   "pretax_growth_rate": (
                       "NOT_APPLICABLE" if i == 0 else
                       _metric_state(_growth_rate(pt, i), economically_invalid=(_v(pt, i - 1) is not None and _v(pt, i - 1) <= 0))
                   ),
                   "net_income_growth_rate": (
                       "NOT_APPLICABLE" if i == 0 else
                       _metric_state(_growth_rate(ni, i), economically_invalid=(_v(ni, i - 1) is not None and _v(ni, i - 1) <= 0))
                   ),
                   "eps_growth_rate": (
                       "NOT_APPLICABLE" if i == 0 else
                       _metric_state(_growth_rate(eps_, i), economically_invalid=(_v(eps_, i - 1) is not None and _v(eps_, i - 1) <= 0))
                   ),
                   "cash_growth_rate": (
                       "NOT_APPLICABLE" if i == 0 else
                       _metric_state(_growth_rate(cash, i), economically_invalid=(_v(cash, i - 1) is not None and _v(cash, i - 1) <= 0))
                   ),
                   "fcf_per_share_growth_rate": (
                       "NOT_APPLICABLE" if i == 0 else
                       _metric_state(_growth_rate(fcf_per_share, i), economically_invalid=(_v(fcf_per_share, i - 1) is not None and _v(fcf_per_share, i - 1) <= 0))
                   ),
               }}
              for i in range(n)]

    secteur = str(metrics.get("Secteur") or "")
    industrie = str(metrics.get("Industrie") or "")
    legacy_score = compute_moat_score(yearly, secteur, industrie)
    score_v3 = compute_buffett_score_v3(
        yearly,
        secteur,
        industrie,
        ticker=symbol,
        company_name=str(metrics.get("Nom") or ""),
    )
    score = float(score_v3["ranking_score"])
    metrics["buffett_rules_score"] = legacy_score
    metrics["score_v3"] = score_v3
    metrics["score_v2"] = score_v3  # alias de migration pour le reporting existant
    metrics.update({
        "score_model_version": score_v3["model_version"],
        "buffett_quality_score": score_v3["buffett_quality_score"],
        "financial_quality_score": score_v3["financial_quality_score"],
        "durability_score": score_v3["durability_score"],
        "financial_moat_proxy_score": score_v3["financial_moat_proxy_score"],
        "capital_allocation_score": score_v3["capital_allocation_score"],
        "dilution_discipline_score": score_v3["dilution_discipline_score"],
        "resilience_score": score_v3["resilience_score"],
        "score_confidence_pct": score_v3["confidence_pct"],
        "score_comparable_to_standard": score_v3["comparable_to_standard"],
        "score_model_complete": score_v3["model_complete"],
        "score_comparison_group": score_v3["comparison_group"],
        "score_business_model": score_v3["business_model"],
        "ranking_score": score,
    })
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
        growth, growth_reliable = select_growth(
            forward, growth_rev, growth_eps,
            extreme=float(Config.GROWTH_EXTREME),
            forward_haircut=float(Config.GROWTH_FORWARD_HAIRCUT),
        )
    except Exception: pass

    metrics.update({"CAGR":growth,"CAGR_Rev":growth_rev,"CAGR_EPS":growth_eps,
                    "CAGR_Forward":forward,"growth_reliable":growth_reliable})
    peg = compute_comparable_peg(
        float(metrics.get("PER") or 0),
        growth,
        growth_reliable=growth_reliable,
        peg_growth_cap=float(Config.PEG_GROWTH_CAP),
    )
    # Métriques adaptées au secteur (P/FFO, PER normalisé, PEG dividende, P/B÷ROE).
    # Le choix des deux axes retenus se fait plus tard, quand tout le secteur est
    # disponible : ici on calcule simplement tout ce qui est calculable.
    try:
        from .sector_valuation import build_valuation_metrics

        metrics["valuation"] = build_valuation_metrics(
            secteur=_canon_sector(str(metrics.get("Secteur") or "")),
            per=metrics.get("PER"),
            growth=growth,
            growth_reliable=growth_reliable,
            peg=peg,
            info_fields=metrics,
            fundamentals=_valuation_fundamentals(income, balance, cashflow),
            peg_growth_cap=float(Config.PEG_GROWTH_CAP),
            dividend_yield_max_pct=float(Config.DIVIDEND_YIELD_MAX_PCT),
            normalized_min_years=int(Config.NORMALIZED_EARNINGS_MIN_YEARS),
            normalized_max_years=int(Config.NORMALIZED_EARNINGS_MAX_YEARS),
        )
    except Exception as exc:  # une métrique optionnelle ne doit jamais casser un run
        print(f"[scoring] valorisation sectorielle indisponible pour {symbol}: {exc}")
    # Le signal final est calculé en batch, une fois tout le secteur disponible,
    # par médiane PER/PEG. Aucune ancienne règle prix/taux globale ne doit fuiter
    # dans la présélection.
    metrics["Achat"] = False
    metrics["PEG"] = peg
    return score, metrics
