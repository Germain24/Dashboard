"""Analyse financière Buffett — wrapper pandas autour de scoring_pure."""

from __future__ import annotations

from .cache_manager import infer_country
from .config import Config
from .scoring_pure import compute_buy_signal, compute_moat_score


def _v(s, i):
    """Valeur scalaire sécurisée depuis Series ou scalaire."""
    try:
        return float(s.iloc[i]) if hasattr(s, "iloc") else float(s)
    except Exception:
        return 0.0


def _b(s, i, growth=False):
    """Valeur booléenne (croissance ou signe)."""
    try:
        if growth:
            return bool(s.diff().iloc[i] > 0) if hasattr(s, "diff") else False
        return bool(s.iloc[i] > 0) if hasattr(s, "iloc") else False
    except Exception:
        return False


def _safe(func, default=0, n=1):
    try:
        import pandas as pd
        r = func()
        if isinstance(r, (pd.Series, pd.DataFrame)):
            r = pd.to_numeric(r, errors="coerce")
        return r.fillna(default) if hasattr(r, "fillna") else (r if r is not None else default)
    except Exception:
        import pandas as pd
        return pd.Series([default] * n)


def extract_metrics(symbol: str, info: dict) -> dict:
    if not info:
        info = {}
    qt = info.get("quoteType", "").upper()
    ln, sn = info.get("longName", ""), info.get("shortName", "")
    secteur = info.get("sector", "Inconnu")
    if qt == "ETF" or "ETF" in ln.upper() or "ETF" in sn.upper():
        secteur = "ETF"
    pays = info.get("country", "Inconnu")
    if pays == "Inconnu":
        pays = infer_country(symbol)
    return {
        "Nom": ln or sn or symbol, "Pays": pays,
        "Prix": info.get("currentPrice", info.get("regularMarketPrice", 0)),
        "EPS": info.get("trailingEps", 0), "PER": info.get("trailingPE", 0),
        "Volume": info.get("volume", info.get("regularMarketVolume", 0)),
        "Secteur": secteur, "QuoteType": qt,
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


def analyze_financials(symbol: str, data: dict) -> tuple[float, dict]:
    """Analyse financière complète → (score 0-100, metrics dict)."""
    import pandas as pd

    info = data.get("info", {})
    metrics = extract_metrics(symbol, info)
    is_etf = metrics.get("Secteur") == "ETF" or metrics.get("QuoteType") == "ETF"
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
            df_[col] = pd.to_numeric(df_[col], errors="coerce").fillna(0)

    n = len(income)
    gpm  = _safe(lambda: income["Gross Profit"] / income["Total Revenue"], 0, n)
    sga  = _safe(lambda: income["Selling General And Administration"] / income["Gross Profit"], 1, n)
    rd   = _safe(lambda: income["Research And Development"] / income["Gross Profit"], 1, n)
    dep  = _safe(lambda: income["Reconciled Depreciation"] / income["Gross Profit"], 1, n)
    inx  = _safe(lambda: income["Interest Expense"] / income["Operating Income"], 1, n)
    pt   = _safe(lambda: income["Pretax Income"], 0, n)
    ni   = _safe(lambda: income["Net Income"], 0, n)
    nim  = _safe(lambda: income["Net Income"] / income["Total Revenue"], 1, n)
    sc   = "Ordinary Shares Number" if "Ordinary Shares Number" in balance.columns else balance.columns[0]
    eps_ = _safe(lambda: income["Net Income"] / balance[sc], 1, n)
    cash = pd.Series([0.0] * n, index=income.index)
    for _cc in ["Cash Cash Equivalents And Short Term Investments", "Inventory", "Accounts Receivable"]:
        if _cc in balance.columns:
            cash = cash + balance[_cc].fillna(0)
    def _roic():
        d = balance.get("Total Debt", balance.get("Current Debt", 0) + balance.get("Long Term Debt And Capital Lease Obligation", 0))
        return income["Operating Income"] / (d + balance["Common Stock Equity"] - balance.get("Cash Cash Equivalents And Short Term Investments", 0))
    roic = _safe(_roic, 0, n)
    dr   = _safe(lambda: balance["Current Debt"] / balance["Long Term Debt And Capital Lease Obligation"], 1, n)
    lr   = _safe(lambda: balance["Total Assets"] / balance["Current Liabilities"], 0, n)
    ltd  = _safe(lambda: balance["Current Debt"] / balance["Pretax Income"], 1, n)
    deq  = _safe(lambda: balance["Total Liabilities Net Minority Interest"] / balance["Common Stock Equity"], 1, n)
    ret  = _safe(lambda: balance["Retained Earnings"], 0, n)
    cv   = _safe(lambda: cashflow["Issuance Of Capital Stock"] + cashflow["Repurchase Of Capital Stock"], 0, n)
    roe_ = _safe(lambda: income["Net Income"] / balance["Stockholders Equity"], 0, n)
    cpx  = _safe(lambda: cashflow["Capital Expenditure"] / income["Net Income"], 1, n)
    bb   = _safe(lambda: -cashflow["Repurchase Of Capital Stock"], 0, n)

    yearly = [{"gpm":_v(gpm,i),"sga":_v(sga,i),"rd":_v(rd,i),"depr":_v(dep,i),"interest_exp":_v(inx,i),
               "pretax_growth":_b(pt,i,True),"net_income_growth":_b(ni,i,True),"net_income_positive":_b(ni,i),
               "nim":_v(nim,i),"eps_growth":_b(eps_,i,True),"cash_growth":_b(cash,i,True),
               "debt_ratio":_v(dr,i),"liab_ratio":_v(lr,i),"lt_debt_ratio":_v(ltd,i),"debt_eq":_v(deq,i),
               "retained_growth":_b(ret,i,True),"cap_stock_var":(_v(cv,i)<0),"roe":_v(roe_,i),
               "roic":_v(roic,i),"capex":_v(cpx,i),"buybacks":(_v(bb,i)>0)} for i in range(n)]

    score = compute_moat_score(yearly)
    growth = growth_rev = growth_eps = None
    try:
        for lbl in ("Total Revenue","Revenue"):
            if lbl in income.columns:
                rv = income[lbl].dropna()
                if len(rv)>=2 and rv.values[0]>0 and rv.values[-1]>0:
                    growth_rev = (rv.values[-1]/rv.values[0])**(1/(len(rv)-1))-1
                break
        ev = [float(e) for e in (eps_.values if hasattr(eps_,"values") else [eps_])]
        if len(ev)>=2 and ev[0]>0 and ev[-1]>0:
            growth_eps = (ev[-1]/ev[0])**(1/(len(ev)-1))-1
        growth = max([g for g in [growth_rev, growth_eps] if g is not None], default=None)
    except Exception: pass

    metrics.update({"CAGR":growth,"CAGR_Rev":growth_rev,"CAGR_EPS":growth_eps})
    achat, peg = compute_buy_signal(
        metrics.get("Secteur","Inconnu"), metrics.get("Pays","Inconnu"),
        float(metrics.get("Prix") or 0), float(metrics.get("EPS") or 0),
        float(metrics.get("PER") or 0), growth,
        Config.TAUX_OBLIGATAIRES, Config.TAUX_DEFAUT, Config.PER_MAX, Config.PEG_MAX,
    )
    metrics["Achat"] = achat
    metrics["PEG"] = peg
    return score, metrics
