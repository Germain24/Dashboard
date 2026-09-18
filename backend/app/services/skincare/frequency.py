"""Logique de fréquence des produits skincare (pure, sans DB).

- quotidien      : dû chaque jour.
- hebdo_jours    : dû les jours de semaine listés (frequence_jours, ex. "0,3").
- n_par_semaine  : flexible — la répartition exacte est décidée par
                   l'orchestrateur hebdomadaire (phases suivantes), pas ici.
"""

from __future__ import annotations

import datetime as dt

from app.models.skincare import SkincareProduct


def is_due_on(product: SkincareProduct, date: dt.date) -> bool:
    if product.frequence_type == "quotidien":
        return True
    if product.frequence_type == "hebdo_jours":
        jours = _parse_jours(product.frequence_jours)
        return date.weekday() in jours
    # n_par_semaine : pas attaché à un jour précis
    return False


def is_flexible(product: SkincareProduct) -> bool:
    """True si la fréquence ne fixe pas de jour précis (n_par_semaine)."""
    return product.frequence_type == "n_par_semaine"


def _parse_jours(raw: str | None) -> set[int]:
    if not raw:
        return set()
    out: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out
