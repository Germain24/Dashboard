"""Look-through pour les contraintes : défensif% et répartition pays par ticker.

Sources (ToutBroker.xlsx) :
- feuille ``ETF_Defensif`` : Defensif_pct par ETF (or + govt souverain + cash +
  secteurs actions défensifs à 100 %).
- feuille ``ETF_Pays`` : répartition pays par ETF (look-through justETF + curé).
- feuille principale : pour les ACTIONS (non-ETF), défensif = 100 % si secteur ∈
  {Santé, Utilities, Conso de base} sinon 0 % ; pays = {Pays: 100 %}.

Sert aux contraintes de l'optimiseur :
  Σ wᵢ·défensifᵢ ≥ MIN_DEFENSIVE_PCT   et   Σ wᵢ·paysᵢ,X ≤ MAX_COUNTRY_PCT  ∀X.
"""

from __future__ import annotations

from .broker_availability import _find_ticker_col, find_broker_file

# Secteurs yfinance considérés défensifs pour une ACTION individuelle.
_DEF_STOCK_SECTORS = {"healthcare", "utilities", "consumer defensive"}
_META = {"Ticker", "Nom", "Region", "Source", "Date_analyse"}


def load_lookthrough(path: str | None = None) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """Retourne (defensif, pays) :
    - ``defensif`` : {ticker_MAJ: fraction défensive 0-1}
    - ``pays``     : {ticker_MAJ: {pays: fraction 0-1}}
    """
    import pandas as pd
    path = path or find_broker_file()
    defensif: dict[str, float] = {}
    pays: dict[str, dict[str, float]] = {}
    if not path:
        return defensif, pays

    # ETF_Defensif
    try:
        d = pd.read_excel(path, sheet_name="ETF_Defensif")
        for _, r in d.iterrows():
            t = str(r.get("Ticker", "")).strip().upper()
            if t:
                defensif[t] = max(0.0, min(float(r.get("Defensif_pct", 0) or 0) / 100.0, 1.0))
    except Exception:
        pass

    # ETF_Pays
    try:
        p = pd.read_excel(path, sheet_name="ETF_Pays")
        ccols = [c for c in p.columns if c not in _META]
        for _, r in p.iterrows():
            t = str(r.get("Ticker", "")).strip().upper()
            if not t:
                continue
            row = {c: float(r[c]) / 100.0 for c in ccols if float(r[c] or 0) > 0}
            if row:
                pays[t] = row
    except Exception:
        pass

    # Actions (feuille principale, non-ETF) : défensif via secteur, pays via Pays.
    try:
        main = pd.read_excel(path, sheet_name=0)
        tcol = _find_ticker_col(main.columns, "Ticker Yahoo Finance")
        if tcol:
            for _, r in main.iterrows():
                t = str(r[tcol]).strip().upper()
                if not t or str(r.get("Secteur 1", "")).strip().upper() == "ETF":
                    continue
                if t not in defensif:
                    sec = str(r.get("Secteur", "")).strip().lower()
                    defensif[t] = 1.0 if sec in _DEF_STOCK_SECTORS else 0.0
                if t not in pays:
                    pp = str(r.get("Pays", "")).strip()
                    if pp and pp.lower() not in ("inconnu", "nan", ""):
                        pays[t] = {pp: 1.0}
    except Exception:
        pass

    return defensif, pays
