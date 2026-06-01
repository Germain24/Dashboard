"""Constantes nutrition — RDA, mapping CSV↔keys, listes de nutriments tracés.

Source : `legacy_code/sante/logic.py`. Les valeurs micronutriments sont les RDA
adulte standard (Santé Canada / EFSA), les seuils Max sont les limites
supérieures conseillées.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# RDA / cibles journalières (hors macros — celles-ci sont calculées par poids)
# ─────────────────────────────────────────────────────────────────────────────

DAILY_BASE_TARGETS_NUTRIENTS: dict[str, float] = {
    "Fibres": 35.0,
    "Sodium_Max": 2000.0,
    "Magnésium": 400.0,
    "Omega3": 2.0,
    "VitA": 900.0,
    "VitB1": 1.2,
    "VitB2": 1.3,
    "VitB3": 16.0,
    "VitB5": 5.0,
    "VitB6": 1.3,
    "VitB9": 400.0,
    "VitB12": 2.4,
    "VitC": 100.0,
    "VitD": 15.0,
    "VitE": 15.0,
    "VitK": 120.0,
    "Calcium": 1000.0,
    "Chlorure": 2300.0,
    "Cuivre": 1.6,
    "Fer": 13.0,
    "Iode": 150.0,
    "Manganèse": 2.3,
    "Phosphore": 700.0,
    "Potassium": 4000.0,
    "Sélénium": 70.0,
    "Zinc": 11.0,
    "Cholesterol_Max": 300.0,
    "Sucres_Max": 50.0,
}

DEFAULT_PRIX_MAX_DAILY: float = 18.0  # CAD/jour, valeur legacy

# Macros non incluses ici : Calories/Protéines/Lipides/Glucides calculées par poids.

# ─────────────────────────────────────────────────────────────────────────────
# Mapping "key métier" (accentué) ↔ colonne CSV (sans accent)
# ─────────────────────────────────────────────────────────────────────────────

NUTRIENT_KEY_TO_CSV: dict[str, str] = {
    "Calories": "Energie",
    "Protéines": "Proteines",
    "Lipides": "Lipides",
    "Glucides": "Glucides",
    "Fibres": "Fibres",
    "Magnésium": "Magnesium",
    "Sodium_Max": "Sodium",
    "Cholesterol_Max": "Cholesterol",
    "Omega3": "Omega 3",
    "VitA": "VitA",
    "VitB1": "VitB1",
    "VitB2": "VitB2",
    "VitB3": "VitB3",
    "VitB5": "VitB5",
    "VitB6": "VitB6",
    "VitB9": "VitB9",
    "VitB12": "VitB12",
    "VitC": "VitC",
    "VitD": "VitD",
    "VitE": "VitE",
    "VitK": "VitK",
    "Calcium": "Calcium",
    "Chlorure": "Chlorure",
    "Cuivre": "Cuivre",
    "Fer": "Fer",
    "Iode": "Iode",
    "Manganèse": "Manganese",
    "Phosphore": "Phosphore",
    "Potassium": "Potassium",
    "Sélénium": "Selenium",
    "Zinc": "Zinc",
    "Sucres_Max": "TotalSugars",  # synthétique = somme de tous les sucres
}

# Inverse pour les totaux
CSV_TO_NUTRIENT_KEY: dict[str, str] = {v: k for k, v in NUTRIENT_KEY_TO_CSV.items()}

# Nutriments "max" : pénalisés quand dépassés, pas quand sous le seuil
TRACKED_MAX_NUTRIENTS: list[str] = ["Sodium_Max", "Cholesterol_Max", "Sucres_Max"]

# Sucres décomposés dans le CSV (somme = TotalSugars)
SUGAR_COMPONENTS: list[str] = ["Glucose", "Fructose", "Galactose", "Saccharose", "Lactose"]

# Aliments "staples" : amorçage du x0 et bonus dans l'optimiseur
STAPLE_KEYWORDS: list[str] = [
    "Riz blanc", "Avoine", "Pois chiche", "Patate",
    "Pates", "Quinoa", "Lentilles",
]

# Clés exclues du calcul de compensation J-1
COMPENSATION_EXCLUDED: set[str] = {"Poids_Corps", "Prix_Max"}
