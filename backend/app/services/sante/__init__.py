"""Module Santé / Nutrition — services métier.

Port + extension de `legacy_code/sante/logic.py` (505 lignes). Découpage :

- `constants`     : nutriments tracés, valeurs RDA, mapping CSV → keys métier
- `intensity`     : helpers intensité de séance + jours sport
- `targets`       : calcul cibles journalières (base + compensation J-1)
- `aliments`      : chargement du catalogue depuis la DB + DataFrame helpers
- `optimizer`     : SLSQP scipy + contraintes (budget, kcal, prot)
- `totals`        : calcul des totaux d'un plan (toutes les valeurs nutritives)
- `projection`    : régression linéaire 30j → date atteinte du poids cible
- `goal`          : helpers singleton NutritionGoal

Les modules `optimizer` et `totals` dépendent de pandas/scipy/numpy ; les
autres restent purs Python pour des tests rapides.
"""

from app.services.sante.constants import (
    DAILY_BASE_TARGETS_NUTRIENTS,
    DEFAULT_PRIX_MAX_DAILY,
    NUTRIENT_KEY_TO_CSV,
    TRACKED_MAX_NUTRIENTS,
)
from app.services.sante.goal import ensure_active_goal, get_active_goal
from app.services.sante.intensity import (
    INTENSITY_LEVELS,
    default_intensity_for_date,
    intensity_modifiers,
)
from app.services.sante.projection import project_weight_to_target
from app.services.sante.targets import calculate_daily_targets

__all__ = [
    "DAILY_BASE_TARGETS_NUTRIENTS",
    "DEFAULT_PRIX_MAX_DAILY",
    "INTENSITY_LEVELS",
    "NUTRIENT_KEY_TO_CSV",
    "TRACKED_MAX_NUTRIENTS",
    "calculate_daily_targets",
    "default_intensity_for_date",
    "ensure_active_goal",
    "get_active_goal",
    "intensity_modifiers",
    "project_weight_to_target",
]
