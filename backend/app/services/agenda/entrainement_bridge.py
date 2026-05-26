"""Pont Agenda ↔ Entraînement via import in-process (PLAN.md notes 11 & 14).

Patron : try/except + fallback silencieux pour ne jamais bloquer Agenda
si le module Entraînement est absent ou lève une exception.

Usage depuis l'API Agenda :
    from app.services.agenda.entrainement_bridge import get_training_block_for_date
    block = get_training_block_for_date(session, date)
    # block est None si pas de séance prévue
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import TYPE_CHECKING, Any, Optional

log = logging.getLogger(__name__)

try:
    from app.services.entrainement import (
        compute_intensity_for_date,
        get_sessions_for_date,
        get_active_program,
        program_day_for_date,
    )
    _HAS_ENTRAINEMENT = True
except ImportError:
    _HAS_ENTRAINEMENT = False
    log.debug("Module Entraînement non disponible — bridge désactivé")


def get_training_block_for_date(
    session: Any,
    date: dt.date,
) -> Optional[dict[str, Any]]:
    """Retourne un bloc de timeline pour la séance du jour, ou None.

    Le bloc est compatible avec le format EvenementRead (virtual=True).
    Priorité :
      1. Séance réellement loggée ce jour (avec durée réelle)
      2. Programme planifié (durée estimée 60 min par défaut)
      3. None si rien
    """
    if not _HAS_ENTRAINEMENT:
        return None
    try:
        seances = get_sessions_for_date(session, date)
        if seances:
            s = seances[0]
            duree = s.duree_min or 60
            debut_dt = s.date if isinstance(s.date, dt.datetime) else dt.datetime.combine(date, dt.time(9, 0))
            fin_dt = debut_dt + dt.timedelta(minutes=duree)
            intensity = compute_intensity_for_date(session, date)
            return {
                "id": None,
                "titre": f"Entraînement — {s.type or 'Séance'}",
                "debut": debut_dt,
                "fin": fin_dt,
                "lieu": "Gym",
                "description": f"Intensité : {intensity} | {duree} min",
                "source": "entrainement",
                "source_id": str(s.id),
                "categorie": "sport",
                "couleur": "#F59E0B",
                "recurrence_id": None,
                "is_virtual": True,
            }

        prog = get_active_program(session)
        if prog:
            pj = program_day_for_date(session, date, programme_id=prog.id)
            if pj and pj.label.lower() not in ("repos", "rest"):
                debut_dt = dt.datetime.combine(date, dt.time(9, 0))
                return {
                    "id": None,
                    "titre": f"Entraînement — {pj.label}",
                    "debut": debut_dt,
                    "fin": debut_dt + dt.timedelta(hours=1),
                    "lieu": "Gym",
                    "description": f"Séance planifiée : {pj.label}",
                    "source": "entrainement",
                    "source_id": None,
                    "categorie": "sport",
                    "couleur": "#F59E0B",
                    "recurrence_id": None,
                    "is_virtual": True,
                }
    except Exception as exc:
        log.warning("Erreur bridge Entraînement→Agenda : %s", exc)
    return None
