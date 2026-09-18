"""Détection de créneaux libres dans une journée.

Algorithme heuristique simple (décision CONV 5) :
  1. Collecter tous les blocs occupés (événements + séance entraînement)
  2. Fusionner les chevauchements
  3. Retourner les trous >= min_duration_min dans [day_start_h, day_end_h]

Logique pure — pas de session DB. Testable sans stack web (PLAN.md note 10).
"""

from __future__ import annotations

import datetime as dt
from typing import Any


def _merge_intervals(
    intervals: list[tuple[dt.datetime, dt.datetime]],
) -> list[tuple[dt.datetime, dt.datetime]]:
    """Fusion des intervalles qui se chevauchent ou se touchent."""
    if not intervals:
        return []
    sorted_iv = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_iv[0]]
    for start, end in sorted_iv[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def free_slots(
    date: dt.date,
    occupied: list[tuple[dt.datetime, dt.datetime]],
    min_duration_min: int = 60,
    day_start_h: int = 7,
    day_end_h: int = 23,
) -> list[dict[str, Any]]:
    """Retourne les créneaux libres de la journée.

    Paramètres :
        date             : la journée à analyser
        occupied         : liste de (debut, fin) des blocs déjà pris
        min_duration_min : durée minimale d'un slot retenu (minutes)
        day_start_h      : heure de début de la journée (défaut 7h)
        day_end_h        : heure de fin de la journée (défaut 23h)

    Retourne une liste de dicts :
        { debut, fin, duree_min }
    """
    day_start = dt.datetime.combine(date, dt.time(day_start_h, 0))
    day_end = dt.datetime.combine(date, dt.time(day_end_h, 0))
    min_delta = dt.timedelta(minutes=min_duration_min)

    # Filtrer aux blocs qui se croisent avec la journée
    in_day = [
        (max(s, day_start), min(e, day_end))
        for s, e in occupied
        if s < day_end and e > day_start
    ]
    merged = _merge_intervals(in_day)

    slots: list[dict[str, Any]] = []
    cursor = day_start
    for block_start, block_end in merged:
        if block_start > cursor and (block_start - cursor) >= min_delta:
            slots.append(
                {
                    "debut": cursor,
                    "fin": block_start,
                    "duree_min": int((block_start - cursor).total_seconds() / 60),
                }
            )
        cursor = max(cursor, block_end)

    # Trou final après le dernier bloc
    if (day_end - cursor) >= min_delta:
        slots.append(
            {
                "debut": cursor,
                "fin": day_end,
                "duree_min": int((day_end - cursor).total_seconds() / 60),
            }
        )
    return slots
