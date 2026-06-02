"""Filtrage et tri génériques via query params réutilisables.

- :class:`Sorting` : dépendance ``?sort=<champ>&order=asc|desc``.
- :func:`apply_sort` : applique le tri à un statement SQLModel, en validant
  que le champ existe sur le modèle (sinon 400).
- :func:`apply_filters` : applique des égalités simples ``champ=valeur``.

Conçu pour se combiner avec :mod:`app.core.pagination`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from fastapi import HTTPException, Query


@dataclass
class Sorting:
    """Dépendance FastAPI : ``?sort=&order=``."""

    sort: Optional[str] = Query(default=None, description="Champ de tri")
    order: str = Query(default="asc", pattern="^(asc|desc)$")


def apply_sort(statement, model: type, sorting: Sorting, *, allowed: Optional[set[str]] = None):
    """Applique un ORDER BY validé. ``allowed`` restreint les champs triables."""
    if not sorting.sort:
        return statement
    if allowed is not None and sorting.sort not in allowed:
        raise HTTPException(400, f"Tri non autorisé sur '{sorting.sort}'")
    col = getattr(model, sorting.sort, None)
    if col is None:
        raise HTTPException(400, f"Champ de tri inconnu : '{sorting.sort}'")
    return statement.order_by(col.desc() if sorting.order == "desc" else col.asc())


def apply_filters(statement, model: type, filters: dict[str, Any]):
    """Applique des filtres d'égalité (les valeurs None sont ignorées)."""
    for field, value in filters.items():
        if value is None:
            continue
        col = getattr(model, field, None)
        if col is None:
            raise HTTPException(400, f"Champ de filtre inconnu : '{field}'")
        statement = statement.where(col == value)
    return statement
