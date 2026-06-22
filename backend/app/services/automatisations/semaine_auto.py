"""Routine « semaine auto » (#210) → délègue au planificateur UNIQUE.

Historiquement un 2e planificateur (sport + études) qui créait des événements
`source="auto_semaine"` en parallèle du planificateur de cycle → doublons de
sport. Fusionné : cette routine n'est plus qu'un raccourci vers le moteur de
cycle unique (`app.services.agenda.auto_plan`), source `"planner"`.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlmodel import Session

from app.services.agenda import auto_plan
from app.services.agenda.planner import TYPE_META


def _block_dict(b) -> dict[str, Any]:
    meta = TYPE_META.get(b.type, {"categorie": "autre", "couleur": None})
    return {
        "titre": b.titre, "debut": b.debut, "fin": b.fin, "type": b.type,
        "categorie": meta["categorie"], "couleur": meta.get("couleur"),
        "source": "planner",
    }


def fill_week_auto(
    session: Session, week_start: dt.date, *, dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Planifie le cycle à partir de `week_start` via le moteur unique.

    `dry_run=True` : aperçu sans écriture. Sinon remplace les blocs `planner` du
    cycle et les réécrit (idempotent). Retourne les blocs (sport, études, repas,
    sommeil, cuisine, révision).
    """
    if dry_run:
        prop = auto_plan.preview(session, week_start)
    else:
        prop, _ = auto_plan.commit(session, week_start)
    return [_block_dict(b) for b in prop.blocks]
