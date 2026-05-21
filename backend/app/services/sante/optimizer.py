"""Optimiseur SLSQP du plan nutrition (port du legacy `optimize_nutrition`).

Différences avec le legacy :
- Lit les aliments depuis la DB (DataFrame fourni par `aliments.load_aliments_dataframe`)
  au lieu de relire le CSV à chaque appel.
- `budget_max_daily` est explicite (paramètre) au lieu d'être lu dans `targets['Prix_Max']`.
  Si None, on utilise `targets.get('Prix_Max', 18.0)`.
- Toute la logique métier (poids des nutriments, contraintes, bounds) est
  conservée à l'identique pour ne pas régresser la qualité des plans.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from app.services.sante.constants import (
    DEFAULT_PRIX_MAX_DAILY,
    NUTRIENT_KEY_TO_CSV,
    STAPLE_KEYWORDS,
    TRACKED_MAX_NUTRIENTS,
)


# Mapping (clé métier → colonne CSV) pour les nutriments utilisés par l'optimiseur.
# On garde uniquement ceux du legacy.
_OPT_NUTRIENT_MAP: list[tuple[str, str]] = [
    ("Calories", "Energie"),
    ("Protéines", "Proteines"),
    ("Lipides", "Lipides"),
    ("Glucides", "Glucides"),
    ("Fibres", "Fibres"),
    ("Magnésium", "Magnesium"),
    ("Sodium_Max", "Sodium"),
    ("Cholesterol_Max", "Cholesterol"),
    ("Omega3", "Omega 3"),
    ("VitA", "VitA"),
    ("VitB1", "VitB1"),
    ("VitB2", "VitB2"),
    ("VitB3", "VitB3"),
    ("VitB5", "VitB5"),
    ("VitB6", "VitB6"),
    ("VitB9", "VitB9"),
    ("VitB12", "VitB12"),
    ("VitC", "VitC"),
    ("VitD", "VitD"),
    ("VitE", "VitE"),
    ("VitK", "VitK"),
    ("Calcium", "Calcium"),
    ("Fer", "Fer"),
    ("Zinc", "Zinc"),
    ("Potassium", "Potassium"),
    ("Iode", "Iode"),
    ("Sélénium", "Selenium"),
    ("Phosphore", "Phosphore"),
    ("Sucres_Max", "TotalSugars"),
]

_WEIGHTS: dict[str, float] = {
    "Energie": 1000.0,
    "Proteines": 1000.0,
    "Lipides": 100.0,
    "Glucides": 100.0,
    "TotalSugars": 500.0,
    "Sodium": 500.0,
    "Cholesterol": 500.0,
}

# Nutriments "max" — clés CSV
_MAX_CSV_COLS: set[str] = {NUTRIENT_KEY_TO_CSV[k] for k in TRACKED_MAX_NUTRIENTS}

MAX_DAILY_UNITS = 4.0  # 1 unité = 100g → 400g/jour max d'un même aliment
SUPPLEMENT_MAX = 0.05   # 5g max pour suppléments / vitamines


def optimize_nutrition(
    df: pd.DataFrame,
    targets: dict[str, float],
    budget_max_daily: Optional[float] = None,
) -> tuple[list[dict[str, Any]] | None, str]:
    """Optimise le plan alimentaire pour atteindre les cibles données.

    Args:
        df: DataFrame issu de `aliments.load_aliments_dataframe`. Index = nom.
        targets: dict de cibles avec au moins Calories, Protéines, Lipides,
                 Glucides, Poids_Corps + les micronutriments.
        budget_max_daily: budget CAD/jour. Si None, prend `targets["Prix_Max"]`
                          ou DEFAULT_PRIX_MAX_DAILY.

    Returns:
        (plan, warning) :
            plan = liste de dicts {Aliment, Quantité, Calories, Protéines, ...}
                   ou None si l'optimisation échoue avec contraintes dures
            warning = message d'avertissement (peut être vide)
    """
    if df.empty:
        return None, "Catalogue aliments vide — impossible d'optimiser."

    if budget_max_daily is None:
        budget_max_daily = float(targets.get("Prix_Max", DEFAULT_PRIX_MAX_DAILY))

    food_names = df.index.tolist()
    num_foods = len(food_names)
    body_weight = float(targets.get("Poids_Corps", 70.0))

    # Liste des (col_csv, target_value, weight) pour l'objective
    nutrient_targets: list[tuple[str, float, float]] = []
    for key, csv_col in _OPT_NUTRIENT_MAP:
        if key not in targets:
            continue
        val = float(targets[key])
        w = _WEIGHTS.get(csv_col, 1.0)
        nutrient_targets.append((csv_col, val, w))

    # Pré-calcul des arrays (perf : on évite df[col].values dans la closure)
    nutrient_arrays: dict[str, np.ndarray] = {
        col: df[col].values for col, _, _ in nutrient_targets
    }
    prix_arr = df["Prix"].values
    cal_arr = df["Energie"].values
    prot_arr = df["Proteines"].values

    def objective(x: np.ndarray) -> float:
        error = 0.0
        for csv_col, target_val, weight in nutrient_targets:
            current = float(np.dot(x, nutrient_arrays[csv_col]))
            eff_target = max(0.0, target_val)
            if eff_target == 0.0:
                # Compensation : on doit consommer 0 (la dette J-1 a déjà été
                # absorbée).Pénaliser tout dépassement.
                if current > 0:
                    error += weight * (current ** 2)
                continue
            rel_error = (current - eff_target) / eff_target
            if csv_col in _MAX_CSV_COLS:
                if current > target_val:
                    error += weight * 5.0 * (rel_error ** 2)
                # sous le max : pas de pénalité
            else:
                error += weight * (rel_error ** 2)

        # Pénalité poids total > 5 % du poids corporel
        total_grams = float(np.sum(x)) * 100.0
        threshold_grams = body_weight * 0.05 * 1000.0
        if total_grams > threshold_grams and threshold_grams > 0:
            excess_ratio = (total_grams - threshold_grams) / threshold_grams
            error += 5000.0 * (excess_ratio ** 2)

        # Petite pénalité prix : favorise les options moins chères à nutrition équivalente
        error += 0.001 * float(np.dot(x, prix_arr))
        return error

    # Contraintes dures : budget, calories min, protéines min
    constraints = [
        {"type": "ineq", "fun": lambda x: budget_max_daily - float(np.dot(x, prix_arr))},
        {"type": "ineq", "fun": lambda x: float(np.dot(x, cal_arr)) - float(targets["Calories"])},
        {"type": "ineq", "fun": lambda x: float(np.dot(x, prot_arr)) - float(targets["Protéines"])},
    ]

    # Bounds : min et max par item (MinQty / MaxQty depuis le CSV)
    # Convention : si la valeur CSV >= 1.0, elle est en grammes (divisée par 100
    # pour obtenir l'unité interne) ; sinon elle est déjà en unités (1 = 100 g).
    def _csv_qty_to_units(v: float) -> float:
        v = float(v or 0)
        if v <= 0:
            return 0.0
        return v / 100.0 if v >= 1.0 else v

    bounds: list[tuple[float, float]] = []
    for name in food_names:
        row = df.loc[name]

        # max
        max_val = MAX_DAILY_UNITS
        max_qty_csv = _csv_qty_to_units(row.get("MaxQty", 0))
        if max_qty_csv > 0:
            max_val = min(max_val, max_qty_csv)
        elif "Supplement" in name or "Vitamine" in name:
            max_val = SUPPLEMENT_MAX

        # min (port + correction du bug legacy : MinQty n'était pas appliqué)
        min_val = _csv_qty_to_units(row.get("MinQty", 0))
        # garde-fous : min ne doit pas dépasser max (sinon SLSQP refuse) ;
        # on borne au max disponible.
        if min_val > max_val:
            min_val = max_val
        bounds.append((min_val, max_val))

    # Initial guess (clampé dans les bounds pour ne pas démarrer infaisable)
    x0 = np.zeros(num_foods)
    for i, name in enumerate(food_names):
        if any(s in name for s in STAPLE_KEYWORDS):
            x0[i] = 1.0
        else:
            x0[i] = 0.05
        lo, hi = bounds[i]
        x0[i] = max(lo, min(x0[i], hi))

    res = minimize(
        objective, x0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-8, "maxiter": 1000},
    )

    if not res.success:
        return None, (
            f"Erreur d'optimisation : {res.message}. Impossible de respecter "
            f"le budget de {budget_max_daily:.2f} CAD tout en s'approchant des objectifs."
        )

    # Warnings post-hoc
    final_price = float(np.dot(res.x, prix_arr))
    final_proteins = float(np.dot(res.x, prot_arr))
    final_calories = float(np.dot(res.x, cal_arr))
    warnings: list[str] = []
    if final_price > budget_max_daily * 1.01:
        warnings.append(f"Budget dépassé de {(final_price - budget_max_daily):.2f} CAD")
    if final_proteins < float(targets["Protéines"]) * 0.98:
        warnings.append(f"Protéines à {final_proteins:.0f}g/{float(targets['Protéines']):.0f}g")
    if final_calories < float(targets["Calories"]) * 0.98:
        warnings.append(f"Calories à {final_calories:.0f}kcal/{float(targets['Calories']):.0f}kcal")
    warning_msg = ("Note : Budget trop serré. " + " | ".join(warnings)) if warnings else ""

    plan: list[dict[str, Any]] = []
    for i, x in enumerate(res.x):
        # Garde tous les items dont la quantité dépasse leur MinQty (ou ~0 si pas
        # de MinQty). Évite de masquer un supplément à très petite dose dont le
        # MinQty est légitime.
        lo = bounds[i][0]
        keep_threshold = max(lo - 1e-9, 1e-9 if lo == 0 else 0.0)
        if x < keep_threshold:
            continue
        name = food_names[i]
        row = df.loc[name]
        qty_val = float(x) * 100.0
        qty_str = f"{qty_val:.0f}g" if qty_val >= 1.0 else f"{qty_val:.2f}g"
        plan.append({
            "Aliment": name,
            "Quantité": qty_str,
            "Quantite_g": qty_val,
            "Calories": float(row["Energie"]) * float(x),
            "Protéines": float(row["Proteines"]) * float(x),
            "Lipides": float(row["Lipides"]) * float(x),
            "Glucides": float(row["Glucides"]) * float(x),
            "Prix": float(row["Prix"]) * float(x),
        })

    return plan, warning_msg
