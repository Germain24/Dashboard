"""Répartition du portefeuille optimal (géographique, sectorielle, défensif/agressif)
affichée dans les logs après l'optimisation.

Sources :
- pays + défensif : look-through (``lookthrough.load_lookthrough`` -> ETF_Pays /
  ETF_Defensif + secteurs défensifs des actions) ;
- classe d'actifs + secteur : classification ToutBroker (Secteur 1-5 pour les ETF,
  colonne Secteur = secteur yfinance pour les actions).

Tout est borné par ce que le look-through connaît (les ETF non renseignés tombent
dans « Inconnu »). Les libellés sont repliés en ASCII avant impression (console
Windows cp1252).
"""
from __future__ import annotations

import unicodedata
from collections import defaultdict


def _ascii(s) -> str:
    """Replie les accents en ASCII (la console Windows cp1252 ne gère pas é, ≥…)."""
    out = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return out or str(s)


# Libellés secteurs -> forme canonique FR (fusionne les doublons EN yfinance / FR ETF).
_SECTOR_CANON = {
    "technology": "Technologie", "technologie": "Technologie",
    "information technology": "Technologie",
    "healthcare": "Sante", "health care": "Sante", "sante": "Sante",
    "financial services": "Finance", "finance": "Finance",
    "financials": "Finance", "banques": "Finance",
    "consumer cyclical": "Conso. discretionnaire",
    "consumer discretionary": "Conso. discretionnaire",
    "conso. discretionnaire": "Conso. discretionnaire",
    "consumer defensive": "Conso. de base", "consumer staples": "Conso. de base",
    "conso. de base": "Conso. de base",
    "energy": "Energie", "energie": "Energie",
    "industrials": "Industrie", "industrie": "Industrie", "industrial": "Industrie",
    "basic materials": "Materiaux", "materiaux": "Materiaux", "materials": "Materiaux",
    "communication services": "Communication", "communication": "Communication",
    "telecoms": "Communication", "telecommunications": "Communication",
    "utilities": "Services aux collectivites",
    "services aux collectivites": "Services aux collectivites",
    # `realestate` (sans espace) provient des clés Yahoo `sectorKey`/`industryKey`
    # et restait non canonisé, d'où un doublon « realestate » dans les répartitions.
    "real estate": "Immobilier", "immobilier": "Immobilier",
    "realestate": "Immobilier", "real-estate": "Immobilier",
    "consumer-cyclical": "Conso. discretionnaire",
    "consumer-defensive": "Conso. de base",
    "financial-services": "Finance", "basic-materials": "Materiaux",
    "communication-services": "Communication",
    # Classification JPX en 33 secteurs (composition officielle TOPIX). Sans ce
    # pont, seul « Real Estate » était reconnu et 98,34 % du TOPIX devenait
    # artificiellement « Inconnu ».
    "electric appliances": "Technologie",
    "precision instruments": "Technologie",
    "banks": "Finance", "insurance": "Finance",
    "securities & commodity futures": "Finance",
    "other financing business": "Finance",
    "information & communication": "Communication",
    "wholesale trade": "Industrie", "machinery": "Industrie",
    "construction": "Industrie", "services": "Industrie",
    "metal products": "Industrie", "land transportation": "Industrie",
    "marine transportation": "Industrie", "air transportation": "Industrie",
    "warehousing & harbor transportation services": "Industrie",
    "chemicals": "Materiaux", "nonferrous metals": "Materiaux",
    "glass & ceramics products": "Materiaux", "iron & steel": "Materiaux",
    "mining": "Materiaux", "pulp & paper": "Materiaux",
    "transportation equipment": "Conso. discretionnaire",
    "retail trade": "Conso. discretionnaire",
    "textiles & apparels": "Conso. discretionnaire",
    "rubber products": "Conso. discretionnaire",
    "other products": "Conso. discretionnaire",
    "foods": "Conso. de base",
    "fishery,agriculture & forestry": "Conso. de base",
    "pharmaceutical": "Sante",
    "oil & coal products": "Energie",
    "electric power & gas": "Services aux collectivites",
    # Métaux précieux : un seul compartiment, sinon deux libellés distincts
    # ouvriraient deux plafonds sectoriels et doubleraient la poche or.
    "or": "Or", "gold": "Or", "or physique": "Or", "physical gold": "Or",
    "metaux precieux": "Or", "precious metals": "Or",
    "metaux precieux physique": "Or",
    "monetaire": "Monetaire", "money market": "Monetaire",
    "obligations souveraines": "Obligations souveraines",
    "government bonds": "Obligations souveraines", "sovereign bonds": "Obligations souveraines",
    "obligations entreprises ig": "Obligations entreprises IG",
    "investment grade corporate bonds": "Obligations entreprises IG",
    "obligations high yield": "Obligations high yield", "high yield bonds": "Obligations high yield",
    "obligations diversifiees": "Obligations diversifiees", "fixed income": "Obligations diversifiees",
    "unknown": "Inconnu", "inconnu": "Inconnu", "n/a": "Inconnu",
}

# Secteurs économiques comparables entre entreprises. Les libellés thématiques
# d'ETF (Eau, Nucléaire, Quality Dividend, Monde...) ne doivent jamais ouvrir
# leur propre plafond sectoriel. ``Or`` reste provisoirement un compartiment de
# risque dédié afin de préserver son plafond historique de 10 %.
ECONOMIC_RISK_SECTORS = {
    "Technologie", "Sante", "Finance", "Conso. discretionnaire",
    "Conso. de base", "Energie", "Industrie", "Materiaux",
    "Communication", "Services aux collectivites", "Immobilier", "Or",
    "Monetaire", "Obligations souveraines", "Obligations entreprises IG",
    "Obligations high yield", "Obligations diversifiees",
}


def _canon_sector(s: str) -> str:
    """Forme canonique FR d'un libellé secteur (ASCII-folded pour le matching)."""
    if not s:
        return "Inconnu"
    return _SECTOR_CANON.get(_ascii(s).strip().lower(), s)


def is_economic_risk_sector(value: str) -> bool:
    return _canon_sector(value) in ECONOMIC_RISK_SECTORS


# Pays EN (justETF / yfinance) -> FR (valeurs déjà ASCII pour la console cp1252).
_COUNTRY_FR = {
    "united states": "Etats-Unis", "united kingdom": "Royaume-Uni",
    "germany": "Allemagne", "france": "France", "japan": "Japon", "china": "Chine",
    "switzerland": "Suisse", "netherlands": "Pays-Bas", "canada": "Canada",
    "australia": "Australie", "sweden": "Suede", "denmark": "Danemark",
    "india": "Inde", "poland": "Pologne", "italy": "Italie", "spain": "Espagne",
    "brazil": "Bresil", "mexico": "Mexique", "taiwan": "Taiwan",
    "south korea": "Coree du Sud", "saudi arabia": "Arabie saoudite",
    "south africa": "Afrique du Sud", "belgium": "Belgique", "finland": "Finlande",
    "norway": "Norvege", "hong kong": "Hong Kong", "ireland": "Irlande",
    "israel": "Israel", "singapore": "Singapour", "new zealand": "Nouvelle-Zelande",
    "portugal": "Portugal", "austria": "Autriche", "chile": "Chili",
    "peru": "Perou", "colombia": "Colombie", "other": "Autres", "inconnu": "Inconnu",
}


def _fr_country(c: str) -> str:
    return _COUNTRY_FR.get(_ascii(c).strip().lower(), c)


def portfolio_breakdown(weights_pct: dict, defmap: dict, paysmap: dict,
                        classmap: dict, sectmap: dict,
                        sector_lookthrough: dict | None = None) -> dict:
    """Agrège l'allocation en répartitions normalisées (somme≈1).

    ``weights_pct`` : {ticker: poids %}. ``defmap`` : {TICKER: fraction défensive
    0-1}. ``paysmap`` : {TICKER: {pays: fraction}}. ``classmap``/``sectmap`` :
    {TICKER: libellé}. Retourne {'pays', 'defensif', 'agressif', 'classe', 'secteur'}.
    """
    from .lookthrough import fill_unknown_countries

    tot = sum(v for v in weights_pct.values() if v and v > 0) or 1.0
    wn = {str(t).upper(): v / tot for t, v in weights_pct.items() if v and v > 0}
    paysmap = fill_unknown_countries(paysmap, list(wn.keys()))
    pays: dict = defaultdict(float)
    pays_contrib: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    classe: dict = defaultdict(float)
    sect: dict = defaultdict(float)
    sect_contrib: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    defv = 0.0
    for t, w in wn.items():
        pm = paysmap.get(t)
        if pm:
            for c, f in pm.items():
                contribution = w * float(f)
                pays[c] += contribution
                pays_contrib[c][t] += contribution
        else:
            pays["Inconnu"] += w
            pays_contrib["Inconnu"][t] += w
        defv += w * float(defmap.get(t, 0.0) or 0.0)
        classe[classmap.get(t, "Inconnu")] += w
        sector_weights = (sector_lookthrough or {}).get(t)
        if sector_weights:
            clean = {
                _canon_sector(sector): max(float(fraction), 0.0)
                for sector, fraction in sector_weights.items()
                if is_economic_risk_sector(sector)
            }
            covered = sum(clean.values())
            if covered > 0:
                for sector, fraction in clean.items():
                    contribution = w * fraction / covered
                    sect[sector] += contribution
                    sect_contrib[sector][t] += contribution
                continue
        raw_sector = sectmap.get(t, "Inconnu")
        sector = _canon_sector(raw_sector) if is_economic_risk_sector(raw_sector) else "Inconnu"
        sect[sector] += w
        sect_contrib[sector][t] += w
    return {
        "pays": dict(pays),
        "pays_contributions": {
            country: dict(values) for country, values in pays_contrib.items()
        },
        "defensif": defv,
        "agressif": max(0.0, 1.0 - defv),
        "classe": dict(classe),
        "secteur": dict(sect),
        "secteur_contributions": {
            sector: dict(values) for sector, values in sect_contrib.items()
        },
    }


def format_breakdown_lines(b: dict, top: int = 12) -> list[str]:
    """Lignes de log ASCII prêtes à imprimer."""
    def _contributors(values: dict[str, float]) -> str:
        return "; ".join(
            f"{_ascii(ticker)} {weight * 100:.1f}%"
            for ticker, weight in sorted(values.items(), key=lambda item: -item[1])
            if weight > 1e-12
        )

    lines = ["[breakdown] === Portefeuille optimal : repartition ==="]
    lines.append("[breakdown] Geographique (look-through):")
    for c, v in sorted(b["pays"].items(), key=lambda x: -x[1])[:top]:
        details = _contributors(b.get("pays_contributions", {}).get(c, {}))
        suffix = f" ({details})" if details else ""
        lines.append(
            f"[breakdown]   {_ascii(_fr_country(c))} {v * 100:.1f}%{suffix}"
        )
    lines.append(
        f"[breakdown] Defensif vs Agressif: {b['defensif'] * 100:.0f}% defensif "
        f"/ {b['agressif'] * 100:.0f}% agressif"
    )
    cl = " | ".join(f"{_ascii(k)} {v * 100:.0f}%"
                    for k, v in sorted(b["classe"].items(), key=lambda x: -x[1]))
    lines.append(f"[breakdown] Classe d'actifs: {cl}")
    lines.append("[breakdown] Secteurs:")
    for sector, value in sorted(b["secteur"].items(), key=lambda item: -item[1])[:top]:
        details = _contributors(
            b.get("secteur_contributions", {}).get(sector, {})
        )
        suffix = f" ({details})" if details else ""
        lines.append(
            f"[breakdown]   {_ascii(sector)} {value * 100:.1f}%{suffix}"
        )
    return lines


def load_classification(path: str | None = None) -> tuple[dict, dict]:
    """(classmap, sectmap) depuis ToutBroker. classe = Secteur 2 (ETF) ou 'Actions'
    (titre vif). secteur = Secteur 4 si ETF sectoriel, sinon classe d'actif large /
    secteur yfinance du titre."""
    import pandas as pd

    from .broker_availability import _find_ticker_col, _secteur1_col
    classmap: dict = {}
    sectmap: dict = {}

    def _col(cols, name):
        for c in cols:
            if str(c).strip().lower() == name:
                return c
        return None

    def _cell(r, c):
        if c is None:
            return ""
        v = r.get(c)
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ""
        s = str(v).strip()
        return "" if s.lower() in ("nan", "none") else s

    try:
        from .broker_availability import load_broker_table, read_broker_excel

        df = read_broker_excel(path) if path else load_broker_table()
        if df is None:
            return classmap, sectmap
        tcol = _find_ticker_col(df.columns, "Ticker Yahoo Finance")
        s1 = _secteur1_col(df.columns)
        c2 = _col(df.columns, "secteur 2")
        c3 = _col(df.columns, "secteur 3")
        c4 = _col(df.columns, "secteur 4")
        cs = _col(df.columns, "secteur")
        for _, r in df.iterrows():
            t = _cell(r, tcol).upper()
            if not t:
                continue
            is_etf = _cell(r, s1).upper() == "ETF"
            s2 = _cell(r, c2)
            s3 = _cell(r, c3)
            s4 = _cell(r, c4)
            sec_plain = _cell(r, cs)
            if is_etf:
                classe = s2 or "Actions"
                if s3.lower() == "sectoriel" and s4:
                    secteur = s4
                elif s2 and s2.lower() != "actions":
                    secteur = s2  # Obligations / Matieres premieres
                else:
                    secteur = "Actions diversifiees"
            else:
                classe = "Actions"
                secteur = sec_plain if sec_plain and sec_plain.upper() != "ETF" else "Inconnu"
            classmap[t] = classe
            sectmap[t] = _canon_sector(secteur)
    except Exception as e:
        print(f"[breakdown] load_classification: {e}")
    return classmap, sectmap


def log_portfolio_breakdown(
    alloc: list[dict],
    *,
    country_exposures: dict | None = None,
    sector_exposures: dict | None = None,
    defensive_exposures: dict | None = None,
) -> None:
    """Calcule et imprime la répartition du portefeuille final.

    Le runner calcule les expositions économiques des ETF à partir des mêmes
    constituants officiels que l'optimiseur. Les recevoir ici est important :
    recharger uniquement le classeur après le run perdrait ces cartes en
    mémoire et ferait apparaître les ETF comme ``Inconnu`` dans le log.
    """
    try:
        from .broker_availability import aggregate_weights
        from .lookthrough import load_lookthrough
        w = aggregate_weights(alloc)
        if not w:
            return
        try:
            defmap, paysmap = load_lookthrough()
        except Exception:
            defmap, paysmap = {}, {}
        # Les cartes produites pendant le run sont la source de vérité la plus
        # fraîche. Elles couvrent aussi les ETF, que load_lookthrough ne lit pas
        # volontairement depuis les anciennes feuilles Excel.
        if defensive_exposures is not None:
            defmap.update(defensive_exposures)
        if country_exposures is not None:
            paysmap.update(country_exposures)
        from .sector_lookthrough import load_sector_lookthrough
        classmap, sectmap = load_classification()
        sector_lookthrough, _ = load_sector_lookthrough()
        if sector_exposures is not None:
            sector_lookthrough.update(sector_exposures)
        b = portfolio_breakdown(
            w, defmap, paysmap, classmap, sectmap, sector_lookthrough
        )
        for line in format_breakdown_lines(b):
            print(line)
    except Exception as e:
        print(f"[breakdown] erreur: {e}")
