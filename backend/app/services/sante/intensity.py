"""Intensité d'entraînement du jour — placeholder V1.

L'orchestrateur a tranché :
- Param optionnel saisi manuellement : `none / low / medium / high`
- Défaut basé sur le jour de la semaine (configurable via `NutritionGoal.sport_days`)
- CONV 7 câblera `/api/entrainement/intensity/today` qui surchargera le placeholder.

Multiplicateurs choisis pour cohérence avec le legacy :
- `medium` reproduit le comportement "jour sport" du legacy
- `none` reproduit le "jour de repos"
- `low` / `high` interpolent autour
"""

from __future__ import annotations

import datetime as dt
from typing import Optional, TypedDict

INTENSITY_LEVELS = ("none", "low", "medium", "high")


class IntensityModifiers(TypedDict):
    """Modificateurs appliqués à la maintenance pour calculer la cible calorique."""

    activity_factor: float        # multiplicateur appliqué à (maintenance + surplus_kcal)
    surplus_kcal: float           # kcal ajoutés à la maintenance avant facteur
    protein_per_kg: float         # g de protéines / kg de poids
    lipid_per_kg: float           # g de lipides / kg de poids


def intensity_modifiers(
    intensity: str,
    surplus_kcal_sport: float = 500.0,
    rest_factor: float = 1.1,
) -> IntensityModifiers:
    """Retourne les modificateurs nutritionnels pour un niveau d'intensité.

    `surplus_kcal_sport` et `rest_factor` viennent du `NutritionGoal` actif.

    - `none`   : jour de repos — maintenance × rest_factor, prot=1.6/kg, lip=1.0/kg
    - `low`    : activité légère — maintenance + 0.4×surplus, ×1.15, prot=1.8, lip=1.1
    - `medium` : équivalent jour sport legacy — (maintenance + surplus) × 1.2,
                 prot=2.2, lip=1.2
    - `high`   : entraînement intense — (maintenance + 1.4×surplus) × 1.25,
                 prot=2.5, lip=1.3
    """
    intensity = (intensity or "none").lower()
    if intensity not in INTENSITY_LEVELS:
        intensity = "none"

    if intensity == "none":
        # surplus_kcal=0 + activity_factor=rest_factor → maintenance × rest_factor
        return IntensityModifiers(
            activity_factor=rest_factor,
            surplus_kcal=0.0,
            protein_per_kg=1.6,
            lipid_per_kg=1.0,
        )
    if intensity == "low":
        return IntensityModifiers(
            activity_factor=1.15,
            surplus_kcal=0.4 * surplus_kcal_sport,
            protein_per_kg=1.8,
            lipid_per_kg=1.1,
        )
    if intensity == "medium":
        return IntensityModifiers(
            activity_factor=1.2,
            surplus_kcal=surplus_kcal_sport,
            protein_per_kg=2.2,
            lipid_per_kg=1.2,
        )
    # high
    return IntensityModifiers(
        activity_factor=1.25,
        surplus_kcal=1.4 * surplus_kcal_sport,
        protein_per_kg=2.5,
        lipid_per_kg=1.3,
    )


def default_intensity_for_date(
    date: dt.date,
    sport_days: Optional[list[int]] = None,
) -> str:
    """Intensité par défaut pour une date donnée.

    `sport_days` : liste d'ISO weekday (Mon=0 … Sun=6) où l'utilisateur s'entraîne.
    Défaut Germain : `[0, 1, 2, 4, 5]` (lun/mar/mer/ven/sam).

    Retourne `medium` si la date tombe sur un jour sport, sinon `none`.
    CONV 7 surchargera ce default avec l'intensité réelle planifiée.
    """
    if sport_days is None:
        sport_days = [0, 1, 2, 4, 5]
    return "medium" if date.weekday() in sport_days else "none"
