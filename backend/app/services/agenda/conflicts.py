"""Détection de conflits d'horaire (#87).

Logique pure : deux intervalles [début, fin) se chevauchent si
`a.debut < b.fin and b.debut < a.fin`. La fin manquante est traitée comme une
durée par défaut d'une heure (cohérent avec le reste du module agenda).
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional

DEFAULT_DURATION = dt.timedelta(hours=1)


def _span(debut: dt.datetime, fin: Optional[dt.datetime]) -> tuple[dt.datetime, dt.datetime]:
    return debut, (fin or debut + DEFAULT_DURATION)


def overlaps(
    a_start: dt.datetime, a_end: Optional[dt.datetime],
    b_start: dt.datetime, b_end: Optional[dt.datetime],
) -> bool:
    a0, a1 = _span(a_start, a_end)
    b0, b1 = _span(b_start, b_end)
    return a0 < b1 and b0 < a1


def find_conflicts(
    debut: dt.datetime,
    fin: Optional[dt.datetime],
    existing: list[dict[str, Any]],
    *,
    ignore_id: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Retourne les événements de `existing` qui chevauchent [debut, fin).

    `existing` : liste de dicts avec au moins `debut` (datetime) et `fin`.
    `ignore_id` : id à ignorer (utile lors d'une modification d'événement).
    """
    out: list[dict[str, Any]] = []
    for e in existing:
        if ignore_id is not None and e.get("id") == ignore_id:
            continue
        e_debut = e.get("debut")
        if not isinstance(e_debut, dt.datetime):
            continue
        if overlaps(debut, fin, e_debut, e.get("fin")):
            out.append(e)
    return out
