"""Calcul des totaux d'un plan (toutes les valeurs nutritives sommées).

Port de `calculate_plan_totals` du legacy. Travaille sur le DataFrame déjà
chargé par `aliments.load_aliments_dataframe` (pas de relecture CSV).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.services.sante.constants import CSV_TO_NUTRIENT_KEY, SUGAR_COMPONENTS


def calculate_plan_totals(
    plan: list[dict[str, Any]],
    df: pd.DataFrame,
) -> dict[str, float]:
    """Somme les nutriments d'un plan.

    Args:
        plan: liste de dicts `{Aliment, Quantite_g, ...}` (sortie de optimize)
              ou `{Aliment, Quantité: "200g", ...}` (legacy).
        df: catalogue aliments transposé (`load_aliments_dataframe`).

    Returns:
        dict { "Calories": 2500.0, "Protéines": 180.0, "Sucres_Max": 45.0, ... }
        Les clés utilisent la convention "accent" du domaine métier.
    """
    totals: dict[str, float] = {}
    for item in plan:
        name = item["Aliment"]
        qty_g = item.get("Quantite_g")
        if qty_g is None:
            qty_str = item.get("Quantité", "0g")
            qty_g = float(str(qty_str).replace("g", "").strip() or 0)
        qty = float(qty_g) / 100.0

        if name not in df.index:
            continue
        row = df.loc[name]

        for col in df.columns:
            val = pd.to_numeric(row[col], errors="coerce")
            if val is None or (isinstance(val, float) and np.isnan(val)):
                continue
            key = CSV_TO_NUTRIENT_KEY.get(col, col)
            totals[key] = totals.get(key, 0.0) + float(val) * qty

        # Sucres : somme des composants si TotalSugars n'a pas fait l'agrégation
        if "Sucres_Max" not in CSV_TO_NUTRIENT_KEY.values() or "TotalSugars" not in df.columns:
            total_sugars = 0.0
            for s in SUGAR_COMPONENTS:
                if s in row:
                    sval = pd.to_numeric(row[s], errors="coerce")
                    if sval is not None and not (isinstance(sval, float) and np.isnan(sval)):
                        total_sugars += float(sval)
            totals["Sucres_Max"] = totals.get("Sucres_Max", 0.0) + total_sugars * qty

    return totals
