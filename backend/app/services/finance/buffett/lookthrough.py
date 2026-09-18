"""Look-through des actions directes pour les contraintes de portefeuille.

Les ETF ne sont jamais lus depuis ``ETF_Defensif`` ou ``ETF_Pays``. Leurs pays
et leur part défensive sont calculés au runtime depuis les actions de l'indice
économique. La feuille principale reste utilisée pour les ACTIONS directes :
défensif = 100 % si secteur ∈
  {Santé, Utilities, Conso de base} sinon 0 % ; pays = {Pays: 100 %}.

Sert aux contraintes de l'optimiseur :
  Σ wᵢ·défensifᵢ ≥ MIN_DEFENSIVE_PCT   et   Σ wᵢ·paysᵢ,X ≤ MAX_COUNTRY_PCT  ∀X.
"""

from __future__ import annotations

from .broker_availability import _find_ticker_col, find_broker_file

# Secteurs yfinance considérés défensifs pour une ACTION individuelle.
_DEF_STOCK_SECTORS = {"healthcare", "utilities", "consumer defensive"}
_META = {
    "Ticker", "Nom", "Region", "Source", "Date_analyse", "ISIN", "Indice",
    "Couverture_pct",
}


def load_lookthrough(path: str | None = None) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """Retourne (defensif, pays) :
    - ``defensif`` : {ticker_MAJ: fraction défensive 0-1}
    - ``pays``     : {ticker_MAJ: {pays: fraction 0-1}}
    """
    defensif: dict[str, float] = {}
    pays: dict[str, dict[str, float]] = {}

    # Actions (feuille principale, non-ETF) : défensif via secteur, pays via Pays.
    try:
        from .broker_availability import load_broker_table, read_broker_excel

        main = read_broker_excel(path) if path else load_broker_table()
        if main is None:
            return defensif, pays
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
                    from .country_normalization import canonical_country

                    pp = canonical_country(r.get("Pays"))
                    if pp != "Inconnu":
                        pays[t] = {pp: 1.0}
    except Exception:
        pass

    return defensif, pays


def fill_unknown_countries(
    pays: dict[str, dict[str, float]], tickers: list[str],
) -> dict[str, dict[str, float]]:
    """Rend toute exposition inconnue explicite, sans inventer sa géographie.

    L'ancien repli copiait la moyenne des autres actifs du portefeuille. Il
    transformait donc une absence de donnée en diversification fictive et faisait
    varier le pays attribué à un même ETF selon les autres candidats du run.
    """
    tickers_u = [str(t).upper() for t in tickers]
    return {
        ticker: dict(pays.get(ticker) or {"Inconnu": 1.0})
        for ticker in tickers_u
    }
