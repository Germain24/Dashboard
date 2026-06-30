"""Persistance du look-through pays des ETF (feuille ``ETF_Pays`` de ToutBroker).

justETF ne fournit PAS la composition des ETF **synthétiques** (swap) — or toute la
gamme PEA Amundi/BNP l'est. Le look-through pays est donc rempli **par indice**
(copie d'un ETF physique du même indice / mono-pays), pas scrapé. Ces helpers
fusionnent ces données dans ``ETF_Pays`` sans écraser l'existant.
"""
from __future__ import annotations

import datetime as dt

# Colonnes NON-pays de ETF_Pays (alignées sur lookthrough._META : Region/Source
# sont des métadonnées de la feuille curée, pas des pays).
_META = ("Ticker", "Nom", "Region", "Source", "Date_analyse")


def _done_pays_tickers(pays_df) -> set[str]:
    """Tickers déjà renseignés en pays (au moins un pays > 0) dans ``ETF_Pays``."""
    import pandas as pd
    done: set[str] = set()
    if pays_df is None or getattr(pays_df, "empty", True):
        return done
    ccols = [c for c in pays_df.columns if c not in _META]
    for _, r in pays_df.iterrows():
        t = str(r.get("Ticker", "") or "").strip()
        if not t:
            continue
        if any((pd.notna(r[c]) and float(r[c] or 0) > 0) for c in ccols):
            done.add(t)
    return done


def _etf_dates(pays_df) -> dict[str, str]:
    """ticker -> Date_analyse (YYYY-MM-DD) depuis ``ETF_Pays``, si la colonne existe."""
    import pandas as pd
    out: dict[str, str] = {}
    if pays_df is None or getattr(pays_df, "empty", True) or "Date_analyse" not in pays_df.columns:
        return out
    for _, r in pays_df.iterrows():
        t = str(r.get("Ticker", "") or "").strip()
        v = r.get("Date_analyse")
        if t and pd.notna(v) and str(v).strip():
            out[t] = str(v).strip()[:10]
    return out


def merge_pays(pays_df, results: list[dict], today: str | None = None):
    """Fusionne les nouveaux pays dans ``ETF_Pays`` (upsert par ticker, union des
    colonnes pays). Préserve lignes/colonnes existantes ; estampille ``Date_analyse``
    = ``today`` pour les ETF (re)remplis, conserve l'ancienne date pour les autres.

    ``results`` : [{Ticker, Nom, pays: {pays: %}}, ...]."""
    import pandas as pd
    today = today or dt.date.today().isoformat()
    rows: dict[str, dict] = {}
    if pays_df is not None and not getattr(pays_df, "empty", True):
        ccols = [c for c in pays_df.columns if c not in _META]
        for _, r in pays_df.iterrows():
            t = str(r.get("Ticker", "") or "").strip()
            if not t:
                continue
            d = r.get("Date_analyse")
            rows[t] = {"Nom": r.get("Nom", ""),
                       "Date_analyse": (str(d)[:10] if pd.notna(d) and str(d).strip() else None)}
            for c in ccols:
                if pd.notna(r[c]) and float(r[c] or 0):
                    rows[t][c] = float(r[c])
    for res in results:
        if not res.get("pays"):
            continue
        rows[res["Ticker"]] = {"Nom": res.get("Nom", ""), "Date_analyse": today,
                               **{k: float(v) for k, v in res["pays"].items()}}
    countries = sorted({c for v in rows.values() for c in v if c not in _META})
    data = []
    for t, v in rows.items():
        row = {"Ticker": t, "Nom": v.get("Nom", ""), "Date_analyse": v.get("Date_analyse")}
        for c in countries:
            row[c] = v.get(c, 0) or 0
        data.append(row)
    df = pd.DataFrame(data)
    if countries and not df.empty:
        order = sorted(countries, key=lambda c: df[c].sum(), reverse=True)
        df = df[["Ticker", "Nom", "Date_analyse"] + order]
    return df


def _read_sheet(path: str, name: str):
    import pandas as pd
    try:
        return pd.read_excel(path, sheet_name=name)
    except Exception:
        return None


def write_pays_lookthrough(results: list[dict], path: str | None = None) -> int:
    """Fusionne ``results`` ([{Ticker, Nom, pays}]) dans la feuille ``ETF_Pays`` de
    ToutBroker en préservant les autres feuilles. Retourne le nombre d'ETF écrits."""
    import pandas as pd
    from .broker_availability import find_broker_file
    path = path or find_broker_file()
    if not path or not results:
        return 0
    pays_df = _read_sheet(path, "ETF_Pays")
    new_pays = merge_pays(pays_df, results)
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as w:
        new_pays.to_excel(w, sheet_name="ETF_Pays", index=False)
    return len(results)
