"""État d'un vêtement : propreté, vie, usure.

Port à l'identique de `legacy_code/habits/logic.py`. Travaille sur des dicts
(items) pour rester utilisable depuis l'optimiseur et depuis les modèles DB —
les wrappers `Vetement → dict` se font dans les routes API.
"""

from __future__ import annotations

from typing import Any


def proprete_pct(item: dict[str, Any]) -> float:
    """Pourcentage de propreté restant avant lavage."""
    p = item.get("portes", 0)
    ep = item.get("etat_propre", 60) or 60
    return max(0.0, 100.0 - (p % ep) * (100.0 / ep))


def vie_pct(item: dict[str, Any]) -> float:
    """Pourcentage de vie restante (usure)."""
    p = item.get("portes", 0)
    ev = item.get("usure_max") or item.get("etat_vie", 500) or 500
    return max(0.0, 100.0 - (p / ev) * 100.0)


def needs_wash(item: dict[str, Any]) -> bool:
    p = item.get("portes", 0)
    ep = item.get("etat_propre", 60) or 60
    return (p % ep == 0) and p > 0


def is_worn_out(item: dict[str, Any]) -> bool:
    return vie_pct(item) <= 0


def ports_avant_lavage(item: dict[str, Any]) -> int:
    p = item.get("portes", 0)
    ep = item.get("etat_propre", 60) or 60
    return int(ep - (p % ep)) if not needs_wash(item) else 0


def disponible(item: dict[str, Any]) -> bool:
    """Un item est portable s'il n'a pas besoin de lavage et n'est pas HS."""
    return not needs_wash(item) and not is_worn_out(item)
