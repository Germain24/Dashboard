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
    "conso. discretionnaire": "Conso. discretionnaire",
    "consumer defensive": "Conso. de base", "conso. de base": "Conso. de base",
    "energy": "Energie", "energie": "Energie",
    "industrials": "Industrie", "industrie": "Industrie", "industrial": "Industrie",
    "basic materials": "Materiaux", "materiaux": "Materiaux", "materials": "Materiaux",
    "communication services": "Communication", "communication": "Communication",
    "telecoms": "Communication", "telecommunications": "Communication",
    "utilities": "Services aux collectivites",
    "services aux collectivites": "Services aux collectivites",
    "real estate": "Immobilier", "immobilier": "Immobilier",
}


def _canon_sector(s: str) -> str:
    """Forme canonique FR d'un libellé secteur (ASCII-folded pour le matching)."""
    if not s:
        return "Inconnu"
    return _SECTOR_CANON.get(_ascii(s).strip().lower(), s)


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
                        classmap: dict, sectmap: dict) -> dict:
    """Agrège l'allocation en répartitions normalisées (somme≈1).

    ``weights_pct`` : {ticker: poids %}. ``defmap`` : {TICKER: fraction défensive
    0-1}. ``paysmap`` : {TICKER: {pays: fraction}}. ``classmap``/``sectmap`` :
    {TICKER: libellé}. Retourne {'pays', 'defensif', 'agressif', 'classe', 'secteur'}.
    """
    tot = sum(v for v in weights_pct.values() if v and v > 0) or 1.0
    wn = {str(t).upper(): v / tot for t, v in weights_pct.items() if v and v > 0}
    pays: dict = defaultdict(float)
    classe: dict = defaultdict(float)
    sect: dict = defaultdict(float)
    defv = 0.0
    for t, w in wn.items():
        pm = paysmap.get(t)
        if pm:
            for c, f in pm.items():
                pays[c] += w * float(f)
        else:
            pays["Inconnu"] += w
        defv += w * float(defmap.get(t, 0.0) or 0.0)
        classe[classmap.get(t, "Inconnu")] += w
        sect[sectmap.get(t, "Inconnu")] += w
    return {
        "pays": dict(pays),
        "defensif": defv,
        "agressif": max(0.0, 1.0 - defv),
        "classe": dict(classe),
        "secteur": dict(sect),
    }


def format_breakdown_lines(b: dict, top: int = 12) -> list[str]:
    """Lignes de log ASCII prêtes à imprimer."""
    lines = ["[breakdown] === Portefeuille optimal : repartition ==="]
    lines.append("[breakdown] Geographique (look-through):")
    for c, v in sorted(b["pays"].items(), key=lambda x: -x[1])[:top]:
        lines.append(f"[breakdown]   {_ascii(_fr_country(c)):22} {v * 100:5.1f}%")
    lines.append(
        f"[breakdown] Defensif vs Agressif: {b['defensif'] * 100:.0f}% defensif "
        f"/ {b['agressif'] * 100:.0f}% agressif"
    )
    cl = " | ".join(f"{_ascii(k)} {v * 100:.0f}%"
                    for k, v in sorted(b["classe"].items(), key=lambda x: -x[1]))
    lines.append(f"[breakdown] Classe d'actifs: {cl}")
    se = " | ".join(f"{_ascii(k)} {v * 100:.0f}%"
                    for k, v in sorted(b["secteur"].items(), key=lambda x: -x[1])[:top])
    lines.append(f"[breakdown] Secteurs: {se}")
    return lines


def load_classification(path: str | None = None) -> tuple[dict, dict]:
    """(classmap, sectmap) depuis ToutBroker. classe = Secteur 2 (ETF) ou 'Actions'
    (titre vif). secteur = Secteur 4 si ETF sectoriel, sinon classe d'actif large /
    secteur yfinance du titre."""
    import pandas as pd

    from .broker_availability import _find_ticker_col, _secteur1_col, find_broker_file
    path = path or find_broker_file()
    classmap: dict = {}
    sectmap: dict = {}
    if not path:
        return classmap, sectmap

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
        df = pd.read_excel(path)
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


def log_portfolio_breakdown(alloc: list[dict]) -> None:
    """Calcule et imprime la répartition du portefeuille final. Best-effort."""
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
        classmap, sectmap = load_classification()
        b = portfolio_breakdown(w, defmap, paysmap, classmap, sectmap)
        for line in format_breakdown_lines(b):
            print(line)
    except Exception as e:
        print(f"[breakdown] erreur: {e}")
