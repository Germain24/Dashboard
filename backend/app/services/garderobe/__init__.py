"""Module Garde-robe - services metier.

Decoupage par responsabilite (port depuis legacy_code/habits/logic.py) :
- state         : proprete, vie, usure
- style         : palette couleurs, score de style
- thermal       : score thermique d'un item, gap a la cible
- weather       : provider OpenWeather + fallback Open-Meteo, cache 30 min
- optimizer     : suggest_outfit(...) avec body coton dans la recherche
- purchase_combos  : conseils d'achat combinatoires (tenues débloquées)

Important :
On n'importe PAS weather ici (dependance httpx) pour que les tests purs
de logique metier puissent tourner sans installer la stack web. Importer
weather depuis le sous-module explicitement.
"""

from app.services.garderobe.constants import EMO_CAT, SLOTS
from app.services.garderobe.optimizer import suggest_outfit
from app.services.garderobe.state import (
    disponible,
    is_worn_out,
    needs_wash,
    ports_avant_lavage,
    proprete_pct,
    vie_pct,
)
from app.services.garderobe.style import (
    colors_compat,
    get_color_category,
    style_score,
)
from app.services.garderobe.thermal import (
    calculate_thermal_gap,
    target_thermal,
    thermal_score,
)

__all__ = [
    "EMO_CAT",
    "SLOTS",
    "calculate_thermal_gap",
    "colors_compat",
    "disponible",
    "get_color_category",
    "is_worn_out",
    "needs_wash",
    "ports_avant_lavage",
    "proprete_pct",
    "style_score",
    "suggest_outfit",
    "target_thermal",
    "thermal_score",
    "vie_pct",
]
