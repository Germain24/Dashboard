"""Remplit Secteur 2/3/4/5 de chaque ETF (Secteur 1 == 'ETF') dans ToutBroker.xlsx.

Hiérarchie (chaque niveau précise le précédent) :
  S1=ETF  >  S2=classe d'actifs  >  S3=catégorie  >  S4=région|secteur  >  S5=précision

Classification dérivée du NOM du fonds par mots-clés. Imparfaite par nature
(noms libres) : à réviser à la main dans l'Excel ensuite. Un backup .bak-* est créé.
"""
from __future__ import annotations

import datetime
import re
import shutil

import pandas as pd

from app.services.finance.buffett.broker_availability import find_broker_file, _secteur1_col


def _w(name: str, *kws: str) -> bool:
    """Vrai si l'un des mots-clés apparaît comme MOT (bornes \\b) dans `name`.

    Évite les faux positifs de sous-chaîne : 'INDE' ne matche pas 'INDEX',
    'MSCI EM' ne matche pas 'MSCI EMU'.
    """
    return any(re.search(r"\b" + re.escape(k) + r"\b", name) for k in kws)


# (mots-clés, région) — testés dans l'ordre (du plus spécifique au plus large)
_REGIONS = [
    (("MSCI WORLD", "FTSE ALL WORLD", "ALL WORLD", "WORLD", "MSCI ACWI", "AC WORLD"), "Monde"),
    (("EMERGING ASIA", "EMERGENTE", "ASIE EMERGENTE"), "Asie émergente"),
    (("LATIN AMERICA", "LATAM", "AMERICA LATINA", "EMERGING LATIN"), "Amérique latine"),
    (("EMERGING EMEA", "EMERGENT EMEA"), "Émergents EMEA"),
    (("ASIA PACIFIC", "ASIE PACIFIQUE", "AC ASIA PACIFIC"), "Asie-Pacifique"),
    # Zone euro AVANT Émergents (sinon 'MSCI EM' attrape 'MSCI EMU') et AVANT Europe.
    (("EURO STOXX", "EUROSTOXX", "MSCI EMU", "EMU", "EUROZONE", "EURO ZONE", "PRIME EUROZONE",
      "EUROLAND", "EURO"), "Zone euro"),
    (("EMERGING", "EMERGENT", "MSCI EM", "EM IMI", "EM BOND", "EMERGING MARK"), "Émergents"),
    (("NASDAQ", "S&P 500", "S&P US", "US TECH", "US INDUSTRIALS", "RUSSELL", "US ENERGY",
      "US SMALLER", "MSCI USA", "US", "SMALLER COMPANIES"), "USA"),
    (("INDIA", "INDE"), "Inde"),
    (("CHINA A", "CHINE", "CHINA"), "Chine"),
    (("JAPON", "JAPAN", "TOPIX"), "Japon"),
    (("BRAZIL", "BRESIL", "BRÉSIL"), "Brésil"),
    (("GREECE", "GRECE", "GRÈCE"), "Grèce"),
    (("POLAND", "POLOGNE"), "Pologne"),
    (("ITALY", "ITALIE", "FTSE MIB", "MIB"), "Italie"),
    (("IBEX",), "Espagne"),
    (("ATX",), "Autriche"),
    (("CAC 40", "CAC40", "MSCI FRANCE", "FRANCE"), "France"),
    (("MDAX", "TECDAX", "LEVDAX", "DIVDAX", "DAX", "GERMANY", "GERMAN", "ALLEMAGNE"), "Allemagne"),
    (("STOXX EUROPE 600", "STOXX EUROPE", "MSCI EUROPE", "EUROPE 600", "DEVELOPED EUROPE",
      "EUROPE"), "Europe"),
]

# (mots-clés, secteur) pour les ETF sectoriels — Robotique AVANT Automobile.
_SECTORS = [
    (("AUTO & ROBO", "ROBOTICS", "ROBO"), "Robotique/IA"),
    (("INFORMATION TECHNOLOGY", "TECHNOLOGY", "US TECH", "TECH", "TECDAX"), "Technologie"),
    (("HEALTH CARE", "HEALTHCARE", "HEALTH"), "Santé"),
    (("FINANCIAL", "FINANCIALS"), "Finance"),
    (("BANKS", "BANQUE", "BANKEN"), "Banques"),
    (("INSURANCE", "ASSURANCE"), "Assurance"),
    (("CLEAN ENERGY", "ENERGY TRANSITION"), "Énergie propre"),
    (("ENERGY", "ENERGIE", "ÉNERGIE", "OIL", "MLP", "ENERGY INFRASTRUCTURE"), "Énergie"),
    (("UTILITIES",), "Services aux collectivités"),
    (("INDUSTRIAL", "INDUSTRIALS", "INDUSTRIE", "INDUSTRIALS & SERVICES"), "Industrie"),
    (("CONSUMER DISCRETIONARY", "CONSUMER DISC"), "Conso. discrétionnaire"),
    (("CONSUMER STAPLES", "CONSUMER STAPL"), "Conso. de base"),
    (("TELECOMMUNICATION", "TELECOM", "TELECOMMUNICATIONS"), "Télécoms"),
    (("BASIC RESOURCES", "MATERIALS", "MATERIAUX"), "Matériaux"),
    (("AUTOMOBILES", "AUTO & PARTS", "AUTOMOBILE"), "Automobile"),
    (("DEFENSE", "DEFENCE", "DÉFENSE"), "Défense"),
    (("WATER", "EAU"), "Eau"),
    (("DIGITAL SECURITY", "CYBER"), "Cybersécurité"),
    (("REAL ESTATE", "IMMOBILIER"), "Immobilier"),
]

# Marqueurs ESG (n'est PAS un secteur : tilt → précision S5)
_ESG = ("ESG", "SRI", "SOCIALLY RESPONSIBLE", "SUSTAINABILITY", "SUSTAINABLE", "SCREENED",
        "CLIMATE", "PARIS ALIGNED", "PARIS-ALIGNED", "TRANSITION", "CTB", "PAB", "GREEN")


def _region(n: str, default: str = "Monde") -> str:
    return next((r for kws, r in _REGIONS if _w(n, *kws)), default)


def classify(name_raw: str) -> tuple[str, str, str, str]:
    n = " " + str(name_raw).upper().replace("-", " ") + " "

    # ── S2 : classe d'actifs ──────────────────────────────────────────────
    is_bond = _w(n, "BOND", "GOVT", "TREASURY", "CORP", "INFLATION", "AT1", "COCO",
                 "AGGREGATE", "GILT", "GILTS", "TIPS", "OBLIG")
    is_money = ("COURT TERME" in n) or _w(n, "MONETAIRE", "MONÉTAIRE", "MONEY MARKET")
    is_commodity = _w(n, "COMMODITY", "COMMODITIES", "GOLD", "SILVER", "PLATINUM", "PALLADIUM",
                      "MATIERE") or "BLOOMBERG COMMODITY" in n
    if is_commodity:
        s2 = "Matières premières"
        if _w(n, "GOLD"): return s2, "Métaux précieux", "Or", "Physique"
        if _w(n, "SILVER"): return s2, "Métaux précieux", "Argent", "Physique"
        if _w(n, "PLATINUM"): return s2, "Métaux précieux", "Platine", "Physique"
        return s2, "Diversifié", "Monde", ("Physique" if "PHYSICAL" in n else "")
    if is_money and not is_bond:
        return "Monétaire", "Court terme", "Zone euro", ""
    if is_bond:
        s2 = "Obligations"
        if _w(n, "INFLATION", "TIPS"): s3 = "Inflation"
        elif "HIGH YIELD" in n: s3 = "High Yield"
        elif _w(n, "AT1", "COCO"): s3 = "Dette subordonnée (AT1/CoCo)"
        elif _w(n, "AGGREGATE"): s3 = "Agrégat"
        elif _w(n, "CORP"): s3 = "Corporate"
        elif _w(n, "GOVT", "TREASURY", "GILT", "GILTS", "GOVERNMENT"): s3 = "Souverain"
        else: s3 = "Diversifié"
        s4 = _region(n, default="Monde")
        if s4 == "Monde" and _w(n, "TREASURY", "US", "USD", "TIPS"): s4 = "USA"
        if s4 == "Monde" and _w(n, "GILT", "GILTS"): s4 = "Royaume-Uni"
        if s4 == "Monde" and ("€" in n or _w(n, "EUR")): s4 = "Zone euro"
        s5 = ""
        for mat in ("0 1YR", "1 3", "3 5", "7 10YR", "7 10", "2 10Y"):
            if mat in n:
                s5 = "Court terme" if mat[0] in "012" else "Moyen/long terme"
                break
        return s2, s3, s4, s5

    # ── S2 = Actions ──────────────────────────────────────────────────────
    s2 = "Actions"

    # Levier / inverse (les '(2x)' deviennent '(2X)' après upper ; '-' -> ' ')
    if _w(n, "LEVERAGED", "LEVDAX") or "(2X)" in n or "2X LEVERAGED" in n:
        return s2, "Levier/Inverse", _region(n), "Levier x2"
    if _w(n, "INVERSE") or "( 1X)" in n or "(1X)" in n:
        return s2, "Levier/Inverse", _region(n), "Inverse -1x"

    # Sectoriel
    sector = next((s for kws, s in _SECTORS if _w(n, *kws)), None)
    if sector:
        return s2, "Sectoriel", sector, _region(n)

    # Facteur / style
    if _w(n, "VALUE"): factor = "Value"
    elif _w(n, "MOMENTUM"): factor = "Momentum"
    elif _w(n, "QUALITY"): factor = "Quality"
    elif _w(n, "MIN VOL", "MIN TE", "LOW VOL") or "MINIMUM VOL" in n: factor = "Min. volatilité"
    elif _w(n, "GROWTH"): factor = "Growth"
    elif _w(n, "SMALL CAP", "SMALL CAPS", "SMALLER COMPANIES") or "RUSSELL 2000" in n: factor = "Small caps"
    elif "EQUAL WEIGHT" in n: factor = "Équipondéré"
    elif _w(n, "DIVIDEND", "DIVIDENDE", "DIVDAX") or "EQUITY INCOME" in n \
            or "SELECT DIVIDEND" in n or "DIVIDEND ARISTOCRATS" in n: factor = "Dividende"
    else: factor = None
    if factor:
        return s2, "Facteur/Style", factor, _region(n)

    # Diversifié (indice large) -> région, puis précision (ESG / couverture / réplication)
    reg = _region(n)
    if _w(n, *_ESG):
        s5 = "ESG"
    elif _w(n, "HEDGED", "COUVERT") or "EUR HEDGED" in n or "CHF HEDGED" in n or "GBP HEDGED" in n:
        s5 = "Couvert (devise)"
    elif _w(n, "SWAP", "SYNTHETIC", "SYNTHÉTIQUE"):
        s5 = "Synthétique"
    else:
        s5 = ""
    return s2, "Diversifié", reg, s5


def main(write: bool = True) -> None:
    p = find_broker_file()
    df = pd.read_excel(p)
    scol = _secteur1_col(df.columns)
    cols = {f"Secteur {i}": next((c for c in df.columns if str(c).strip().lower() == f"secteur {i}"), None)
            for i in range(2, 6)}
    mask = df[scol].astype(str).str.strip().str.upper() == "ETF"

    for idx in df[mask].index:
        s2, s3, s4, s5 = classify(df.at[idx, "Nom"])
        for i, val in zip(range(2, 6), (s2, s3, s4, s5)):
            df.at[idx, cols[f"Secteur {i}"]] = val

    # Affichage pour revue
    show = df.loc[mask, ["Ticker Yahoo Finance", "Nom"] + [cols[f"Secteur {i}"] for i in range(2, 6)]]
    for _, r in show.iterrows():
        vals = " > ".join(str(r[cols[f"Secteur {i}"]]) for i in range(2, 6))
        print(f"{str(r['Ticker Yahoo Finance']):14} {vals}")

    if write:
        bak = p.replace(".xlsx", f".bak-{datetime.datetime.now():%Y%m%d-%H%M%S}.xlsx")
        shutil.copy2(p, bak)
        df.to_excel(p, index=False)
        print(f"\n[OK] {int(mask.sum())} ETF classés. Backup: {bak}")


if __name__ == "__main__":
    import sys
    main(write="--dry" not in sys.argv)
