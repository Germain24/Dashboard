"""Ventilation cohérente des coûts d'un lieu, avec fallbacks transparents."""
from __future__ import annotations

from app.models.voyage import LieuVoyage

_PREMIUM = (
    "diving", "plong", "safari", "cruise", "croisi", "expedition",
    "marathon", "ski", "balloon", "hélicopt", "helicopt",
)
_PAID = (
    "museum", "musée", "castle", "château", "tower", "temple",
    "palace", "palais", "tour ", "wine", "food scene",
)
_LOW_COST = (
    "hiking", "walk", "beach", "plage", "park", "parc", "reserve",
    "réserve", "waterfall", "chute", "mount", "mont ", "old town",
)


def _daily_split(lieu: LieuVoyage) -> tuple[float, float, str]:
    total = max(0.0, float(lieu.cout_jour_estime or 0.0))
    lodging = lieu.cout_hebergement_jour
    food = lieu.cout_nourriture_jour
    if lodging is not None and food is not None:
        return float(lodging), float(food), "renseigné"
    if lodging is not None:
        return float(lodging), max(0.0, total - float(lodging)), "partiellement_estimé"
    if food is not None:
        return max(0.0, total - float(food)), float(food), "partiellement_estimé"
    # Le coût/jour historique couvrait déjà la vie sur place. On le ventile,
    # sans l'ajouter une seconde fois au total.
    return round(total * 0.65, 2), round(total * 0.35, 2), "estimé"


def estimate_activity_cost(lieu: LieuVoyage) -> tuple[float, str]:
    if lieu.cout_activite is not None:
        return float(lieu.cout_activite), "renseigné"
    name = lieu.nom.casefold()
    daily = max(30.0, float(lieu.cout_jour_estime or 0.0))
    days = max(1, min(int(lieu.jours_min or 1), 4))
    factor = 0.30
    if any(token in name for token in _PREMIUM):
        factor = 0.90
    elif any(token in name for token in _PAID):
        factor = 0.45
    elif any(token in name for token in _LOW_COST):
        factor = 0.18
    return round(max(15.0, daily * days * factor), 2), "estimé"


def estimate_local_cost(lieu: LieuVoyage) -> tuple[float, str]:
    if lieu.cout_transport_local is not None:
        return float(lieu.cout_transport_local), "renseigné"
    daily = max(30.0, float(lieu.cout_jour_estime or 0.0))
    days = max(1, min(int(lieu.jours_min or 1), 5))
    return round(max(20.0, daily * days * 0.18), 2), "estimé"


def cost_breakdown(lieu: LieuVoyage, days: int | None = None) -> dict:
    lodging_day, food_day, daily_source = _daily_split(lieu)
    activity, activity_source = estimate_activity_cost(lieu)
    local, local_source = estimate_local_cost(lieu)
    stay_days = max(0, int(days if days is not None else (lieu.jours_min or 0)))
    return {
        "hebergement_jour": lodging_day,
        "nourriture_jour": food_day,
        "cout_jour": lodging_day + food_day,
        "hebergement": round(lodging_day * stay_days, 2),
        "nourriture": round(food_day * stay_days, 2),
        "activite": activity,
        "transport_local": local,
        "source_journalier": daily_source,
        "source_activite": activity_source,
        "source_local": local_source,
    }
