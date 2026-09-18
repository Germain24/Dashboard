"""Normalisation de la table CIQUAL 2020 (ANSES) vers les colonnes du dépôt.

La table brute (`data/imports/Sante/ciqual/Table_Ciqual_2020_FR.xls`, licence
ouverte Etalab) porte 3 186 aliments × 76 composants. `aliments.csv` en attend
45, sous d'autres noms et parfois comme somme de plusieurs composants CIQUAL.
Ce module ne fait que la traduction — logique PURE, sans I/O : le script
`scripts/import_ciqual.py` lit le fichier et écrit le CSV normalisé.

Pourquoi CIQUAL et pas les étiquettes produit : les micronutriments (iode,
sélénium, vitamine K…) sont ce que l'optimiseur cherche à couvrir, et ils sont
quasi absents des bases de produits emballés. Mesuré le 2026-08-11 sur 30
codes-barres Super C tirés au sort dans Open Food Facts : 40 % de produits
trouvés, 37 % avec des protéines, **17 % avec ne serait-ce qu'un micro**.

Limite à garder en tête : CIQUAL décrit des aliments GÉNÉRIQUES français. Un
produit canadien rattaché à une entrée CIQUAL hérite d'un profil plausible, pas
de son étiquette réelle. C'est suffisant pour optimiser un panier, pas pour
annoncer une valeur nutritionnelle exacte.
"""
from __future__ import annotations

import re
from typing import Optional

#: Colonnes d'identité conservées telles quelles.
IDENTITY_COLUMNS: dict[str, str] = {
    "alim_code": "CiqualCode",
    "alim_nom_fr": "CiqualNom",
    "alim_grp_nom_fr": "CiqualGroupe",
    "alim_ssgrp_nom_fr": "CiqualSousGroupe",
}

#: colonne du dépôt -> composant CIQUAL unique (même unité de part et d'autre :
#: g et mg pour les macros/minéraux, µg pour A, D, K, B9, B12, iode, sélénium —
#: vérifié contre les RDA de `constants.DAILY_BASE_TARGETS_NUTRIENTS`).
SIMPLE_MAP: dict[str, str] = {
    "Energie": "Energie, Règlement UE N° 1169/2011 (kcal/100 g)",
    "Proteines": "Protéines, N x facteur de Jones (g/100 g)",
    "Glucides": "Glucides (g/100 g)",
    "Lipides": "Lipides (g/100 g)",
    "Amidon": "Amidon (g/100 g)",
    "Fibres": "Fibres alimentaires (g/100 g)",
    "Polyols": "Polyols totaux (g/100 g)",
    "Glucose": "Glucose (g/100 g)",
    "Fructose": "Fructose (g/100 g)",
    "Galactose": "Galactose (g/100 g)",
    "Saccharose": "Saccharose (g/100 g)",
    "Lactose": "Lactose (g/100 g)",
    "AG satures": "AG saturés (g/100 g)",
    "AG monoinsatures": "AG monoinsaturés (g/100 g)",
    "Cholesterol": "Cholestérol (mg/100 g)",
    "Sodium": "Sodium (mg/100 g)",
    "Magnesium": "Magnésium (mg/100 g)",
    "Calcium": "Calcium (mg/100 g)",
    "Chlorure": "Chlorure (mg/100 g)",
    "Cuivre": "Cuivre (mg/100 g)",
    "Fer": "Fer (mg/100 g)",
    "Iode": "Iode (µg/100 g)",
    "Manganese": "Manganèse (mg/100 g)",
    "Phosphore": "Phosphore (mg/100 g)",
    "Potassium": "Potassium (mg/100 g)",
    "Selenium": "Sélénium (µg/100 g)",
    "Zinc": "Zinc (mg/100 g)",
    "VitD": "Vitamine D (µg/100 g)",
    "VitE": "Vitamine E (mg/100 g)",
    "VitC": "Vitamine C (mg/100 g)",
    "VitB1": "Vitamine B1 ou Thiamine (mg/100 g)",
    "VitB2": "Vitamine B2 ou Riboflavine (mg/100 g)",
    "VitB3": "Vitamine B3 ou PP ou Niacine (mg/100 g)",
    "VitB5": "Vitamine B5 ou Acide pantothénique (mg/100 g)",
    "VitB6": "Vitamine B6 (mg/100 g)",
    "VitB9": "Vitamine B9 ou Folates totaux (µg/100 g)",
    "VitB12": "Vitamine B12 (µg/100 g)",
}

#: Colonnes du dépôt obtenues en SOMMANT plusieurs composants CIQUAL.
#: - Omega 3 : ALA + EPA + DHA (les trois que CIQUAL détaille) ;
#: - Omega 6 : linoléique + arachidonique ;
#: - VitK    : K1 (phylloquinone) + K2 (ménaquinones), la cible de 120 µg
#:             portant sur la vitamine K totale.
SUM_MAP: dict[str, tuple[str, ...]] = {
    "Omega 3": (
        "AG 18:3 c9,c12,c15 (n-3), alpha-linolénique (g/100 g)",
        "AG 20:5 5c,8c,11c,14c,17c (n-3) EPA (g/100 g)",
        "AG 22:6 4c,7c,10c,13c,16c,19c (n-3) DHA (g/100 g)",
    ),
    "Omega 6": (
        "AG 18:2 9c,12c (n-6), linoléique (g/100 g)",
        "AG 20:4 5c,8c,11c,14c (n-6), arachidonique (g/100 g)",
    ),
    "VitK": (
        "Vitamine K1 (µg/100 g)",
        "Vitamine K2 (µg/100 g)",
    ),
}

#: Rétinol pur (µg) et bêta-carotène (µg), combinés en équivalents d'activité du
#: rétinol : 12 µg de bêta-carotène alimentaire valent 1 µg de rétinol (facteur
#: RAE de l'Institute of Medicine, celui qui sous-tend la RDA de 900 µg utilisée
#: dans `constants`). Additionner les µg bruts surestimerait grossièrement la
#: vitamine A des légumes orange.
VITA_RETINOL = "Rétinol (µg/100 g)"
VITA_BETACAROTENE = "Beta-Carotène (µg/100 g)"
BETACAROTENE_TO_RETINOL = 12.0

#: Repli quand la colonne protéines « facteur de Jones » est vide.
PROTEINES_FALLBACK = "Protéines, N x 6.25 (g/100 g)"

#: Composants nécessaires au calcul de l'énergie quand elle n'est pas tabulée.
ALCOOL = "Alcool (g/100 g)"
ACIDES_ORGANIQUES = "Acides organiques (g/100 g)"

#: Coefficients de conversion énergétique du règlement UE n° 1169/2011,
#: annexe XIV — les mêmes que ceux dont CIQUAL se sert pour la colonne
#: « Energie, Règlement UE ». {colonne du dépôt ou CIQUAL: kcal par gramme}.
ENERGY_FACTORS: dict[str, float] = {
    "Proteines": 4.0,
    "Glucides": 4.0,      # glucides assimilables, polyols exclus (convention CIQUAL)
    "Lipides": 9.0,
    "Fibres": 2.0,
    "Polyols": 2.4,
    "Alcool": 7.0,
    "AcidesOrganiques": 3.0,
}

_LESS_THAN_RE = re.compile(r"^<\s*(.+)$")
_NUMBER_RE = re.compile(r"^-?[\d.]+$")


def parse_value(raw: object) -> Optional[float]:
    """Convertit une cellule CIQUAL en float, ou None si la teneur est inconnue.

    Quatre formes existent dans la table (relevé exhaustif sur les 76 colonnes) :
    un nombre à virgule décimale (« 21,6 »), « - » (non déterminé), « traces »,
    et « < X » (sous le seuil de quantification).

    Conventions retenues :
    - « traces »  -> 0.0 : présence réelle mais négligeable, la compter à zéro
      ne peut que SOUS-estimer la couverture, jamais la gonfler ;
    - « < X »     -> X/2 : milieu de l'intervalle [0, X], usage courant pour les
      données censurées à gauche ;
    - « - »       -> None : teneur INCONNUE, à distinguer d'un vrai zéro. Le
      choix de ce qu'on en fait appartient à l'appelant.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text in {"-", "nan", "NaN"}:
        return None
    if "race" in text.lower():          # « traces », « Traces »
        return 0.0
    # Espaces (y compris insécables) servant de séparateur de milliers.
    text = text.replace(" ", "").replace(" ", "").replace(",", ".")
    less_than = _LESS_THAN_RE.match(text)
    if less_than:
        inner = less_than.group(1)
        if _NUMBER_RE.match(inner):
            return float(inner) / 2.0
        return None
    if _NUMBER_RE.match(text):
        return float(text)
    return None


def _first_available(row: dict, columns: tuple[str, ...]) -> Optional[float]:
    for col in columns:
        value = parse_value(row.get(col))
        if value is not None:
            return value
    return None


def _sum_available(row: dict, columns: tuple[str, ...]) -> Optional[float]:
    """Somme des composants CONNUS ; None si aucun ne l'est.

    Un composant inconnu vaut 0 dans la somme dès lors qu'au moins un autre est
    connu : pour les oméga-3, ignorer un EPA non déterminé vaut mieux que de
    jeter l'ALA qui, lui, est mesuré.
    """
    values = [parse_value(row.get(col)) for col in columns]
    known = [v for v in values if v is not None]
    return sum(known) if known else None


def convert_row(row: dict) -> dict[str, float]:
    """Une ligne CIQUAL brute -> {colonne du dépôt: valeur}.

    Les teneurs inconnues sont OMISES du résultat (et non mises à zéro) : c'est
    à l'appelant de décider. `aliments.load_aliments_dataframe` traite déjà une
    cellule vide comme 0.0, ce qui revient à ne jamais créditer un aliment d'un
    nutriment qu'on ne lui connaît pas — le sens voulu.
    """
    out: dict[str, float] = {}

    for repo_col, ciqual_col in SIMPLE_MAP.items():
        value = parse_value(row.get(ciqual_col))
        if value is None and repo_col == "Proteines":
            value = parse_value(row.get(PROTEINES_FALLBACK))
        if value is not None:
            out[repo_col] = value

    for repo_col, ciqual_cols in SUM_MAP.items():
        value = _sum_available(row, ciqual_cols)
        if value is not None:
            out[repo_col] = value

    retinol = parse_value(row.get(VITA_RETINOL))
    carotene = parse_value(row.get(VITA_BETACAROTENE))
    if retinol is not None or carotene is not None:
        out["VitA"] = (retinol or 0.0) + (carotene or 0.0) / BETACAROTENE_TO_RETINOL

    if "Energie" not in out:
        derived = derive_energy(out, row)
        if derived is not None:
            out["Energie"] = derived

    return out


def derive_energy(converted: dict[str, float], row: dict) -> Optional[float]:
    """Énergie (kcal/100 g) recalculée depuis les macros, ou None si impossible.

    CIQUAL laisse l'énergie vide pour 888 de ses 3 186 aliments — essentiellement
    des plats composés (salades appertisées, préparations « aliment moyen ») —
    alors que leurs protéines, lipides et glucides sont bien renseignés à plus de
    99 %. Sans ce calcul, ces aliments entreraient au catalogue avec 0 kcal :
    l'optimiseur, qui doit atteindre une cible calorique, les verrait comme une
    couverture gratuite en micronutriments et en empilerait des quantités
    absurdes. Le trou est donc dangereux, pas seulement gênant.

    On applique les coefficients de l'annexe XIV du règlement UE n° 1169/2011,
    ceux-là mêmes dont CIQUAL se sert pour sa propre colonne — le résultat est
    homogène avec les valeurs tabulées, pas une approximation d'une autre école.

    Renvoie None si aucune des trois macros principales n'est connue : mieux vaut
    un aliment sans énergie, écarté plus tard, qu'une valeur inventée.
    """
    extra = {
        "Alcool": parse_value(row.get(ALCOOL)),
        "AcidesOrganiques": parse_value(row.get(ACIDES_ORGANIQUES)),
    }
    if all(converted.get(m) is None for m in ("Proteines", "Lipides", "Glucides")):
        return None
    total = 0.0
    for component, factor in ENERGY_FACTORS.items():
        value = extra[component] if component in extra else converted.get(component)
        if value is not None:
            total += value * factor
    return total


def identity(row: dict) -> dict[str, str]:
    """Code, nom et groupes CIQUAL d'une ligne, en texte."""
    return {
        repo_col: str(row.get(ciqual_col) or "").strip()
        for ciqual_col, repo_col in IDENTITY_COLUMNS.items()
    }
