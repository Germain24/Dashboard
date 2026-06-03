"""Bloc de temps « focus » Études → Agenda (#89).

Planifie une session de travail en plaçant un bloc de `duree_min` dans le
premier créneau libre suffisant de la journée (réutilise free_slots, #92), puis
crée un Evenement agenda catégorisé « etudes ».

`pick_slot` est pur (testable) ; la route gère la persistance.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional


def pick_slot(slots: list[dict[str, Any]], duree_min: int) -> Optional[dict[str, dt.datetime]]:
    """Premier créneau libre pouvant accueillir `duree_min`.

    `slots` : sortie de free_slots (`{debut, fin, duree_min}`).
    Retourne `{debut, fin}` (fin = debut + duree_min) ou None.
    """
    for s in slots:
        if int(s.get("duree_min", 0)) >= duree_min:
            debut = s["debut"]
            return {"debut": debut, "fin": debut + dt.timedelta(minutes=duree_min)}
    return None
