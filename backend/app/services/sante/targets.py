"""Calcul des cibles journalières (port `calculate_daily_targets` + intensité).

Différences avec le legacy :
- L'intensité d'entraînement est explicite (paramètre + défaut date-based)
  au lieu d'être implicite (lun-ven = sport, sam-dim = repos)
- Les coefficients `surplus_kcal_sport` et `rest_factor` viennent du
  `NutritionGoal` actif au lieu d'être codés en dur
- La compensation J-1 est plafonnée si elle dépasse certains seuils raisonnables
  (sinon une cible négative crée un objectif "0" qu'on peut difficilement
  atteindre — comportement legacy conservé)
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from app.services.sante.constants import (
    COMPENSATION_EXCLUDED,
    DAILY_BASE_TARGETS_NUTRIENTS,
    DEFAULT_PRIX_MAX_DAILY,
)
from app.core.config import settings
from app.services.sante.intensity import default_intensity_for_date, intensity_modifiers


def calculate_daily_targets(
    weight: float,
    date: dt.date,
    history: list[dict[str, Any]] | None = None,
    intensity: Optional[str] = None,
    surplus_kcal_sport: float = settings.sante_surplus_kcal_sport,
    rest_factor: float = settings.sante_rest_factor,
    sport_days: Optional[list[int]] = None,
    prix_max_daily: float = DEFAULT_PRIX_MAX_DAILY,
) -> tuple[dict[str, float], dict[str, float]]:
    """Calcule les cibles journalières (base + compensées par le gap J-1).

    Args:
        weight: poids du jour (kg)
        date: date du jour
        history: liste de plans précédents (chacun = dict avec date, targets,
                 consumed — peut venir de `PlanNutrition.dict()`)
        intensity: 'none' / 'low' / 'medium' / 'high'. Si None, calcul auto
                   selon `sport_days`.
        surplus_kcal_sport: surplus calorique pour un jour sport (default 500)
        rest_factor: multiplicateur sur la maintenance en jour de repos
        sport_days: ISO weekday list. None = défaut [0,1,2,4,5] (Germain)
        prix_max_daily: budget alimentaire CAD/jour

    Returns:
        (base_targets, comp_targets) : base sans compensation, comp avec gap J-1
    """
    if intensity is None:
        intensity = default_intensity_for_date(date, sport_days)

    mods = intensity_modifiers(intensity, surplus_kcal_sport, rest_factor)

    p = weight
    maintenance = p * settings.sante_maintenance_kcal_per_kg

    # Calories : (maintenance + surplus) × activity_factor pour rester
    # comparable au legacy ((maintenance + 500) × 1.2 en sport day)
    cals = (maintenance + mods["surplus_kcal"]) * mods["activity_factor"]
    proteins = p * mods["protein_per_kg"]
    lipids = p * mods["lipid_per_kg"]
    glucides = (cals - (proteins * 4.0) - (lipids * 9.0)) / 4.0

    base_daily: dict[str, float] = {
        "Calories": cals,
        "Protéines": proteins,
        "Lipides": lipids,
        "Glucides": glucides,
        **DAILY_BASE_TARGETS_NUTRIENTS,
        "Prix_Max": prix_max_daily,
        "Poids_Corps": p,
    }

    # ── Compensation J-1 ──
    comp_targets = dict(base_daily)

    if history:
        yesterday = date - dt.timedelta(days=1)
        y_entry = _find_entry_for_date(history, yesterday)
        if y_entry:
            y_targets = y_entry.get("targets") or {}
            y_consumed = y_entry.get("consumed") or {}
            if y_targets and y_consumed:
                # Cas legacy "targets hebdo" : un Calories > 10000 = ancien
                # système. On compense au 1/7e.
                is_weekly = (y_targets.get("Calories", 0) or 0) > 10000
                for k in base_daily:
                    if k in COMPENSATION_EXCLUDED:
                        continue
                    if k in y_targets and k in y_consumed:
                        gap = y_targets[k] - y_consumed[k]
                        if is_weekly:
                            gap /= 7.0
                        comp_targets[k] += gap

    return base_daily, comp_targets


def _find_entry_for_date(history: list[dict[str, Any]], date: dt.date) -> dict | None:
    """Cherche un plan pour une date donnée dans une liste hétérogène.

    Tolère `date` en str ISO ou en `dt.date`/`dt.datetime` (selon source : JSON
    legacy vs. SQLModel dict).
    """
    iso = date.isoformat()
    for e in history:
        ed = e.get("date")
        if isinstance(ed, str):
            if ed == iso:
                return e
        elif isinstance(ed, dt.datetime):
            if ed.date() == date:
                return e
        elif isinstance(ed, dt.date):
            if ed == date:
                return e
    return None
