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
                # Séance planifiée mais pas encore loggée : aucun horaire imposé.
                # fin=None = bloc « flexible » — il n'occupe aucun créneau
                # (free_slots ignore les blocs sans fin) et n'apparaît pas
                # comme un événement à heure fixe dans les vues semaine/mois.
                return {
                    "id": None,
                    "titre": f"Entraînement — {pj.label}",
                    "debut": dt.datetime.combine(date, dt.time.min),
                    "fin": None,
                    "lieu": "Gym",
                    "description": f"Séance planifiée : {pj.label} · horaire libre",
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


_WORKOUT_KEYWORDS = (
    "entraînement", "entrainement", "musculation", "muscu",
    "gym", "workout", "fitness", "cardio", "séance", "seance",
)


def _looks_like_workout(titre: Optional[str]) -> bool:
    """Vrai si le titre évoque une séance de sport/muscu, quel que soit le
    vocabulaire exact (l'utilisateur peut avoir nommé sa récurrence Google
    Calendar « Musculation », « Gym », etc. — pas forcément « Entraînement »)."""
    if not titre:
        return False
    lowered = titre.lower()
    return any(kw in lowered for kw in _WORKOUT_KEYWORDS)


def _same_day(a: Optional[Any], b: Optional[Any]) -> bool:
    """Vrai si `a` et `b` tombent le même jour. Permissif (True) quand l'une
    des deux dates manque : les tests historiques passent des dicts
    minimalistes sans `debut`, et en production `get_training_block_for_date`
    fournit toujours un `debut`, donc ce cas ne se présente pas réellement."""
    if a is None or b is None:
        return True
    da = a.date() if isinstance(a, dt.datetime) else a
    db = b.date() if isinstance(b, dt.datetime) else b
    return da == db


def dedupe_sport_events(
    events: list[dict[str, Any]],
    training: Optional[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Retire les événements « sport » (récurrence/ponctuel/import externe)
    redondants avec le bloc Entraînement du jour.

    Avant le module Entraînement, l'utilisateur avait ses propres événements/
    récurrences « catégorie sport » (ex. une règle hebdo « Musculation »).
    Une fois un programme actif, le bridge produit un bloc plus précis
    (« Entraînement — Pull/Push/Legs ») pour le même jour : sans ce filtre,
    les deux coexistent et la séance apparaît deux fois dans l'agenda.

    Un événement est retiré s'il tombe le même jour que le bloc ET que :
      - il porte `categorie == "sport"` (tag manuel), OU
      - son titre évoque un entraînement (import Google Calendar / .ics —
        ces sources ne renseignent jamais `categorie`, donc le tag seul ne
        suffit pas à les détecter, #doublon muscu).
    """
    if not training:
        return events
    training_debut = training.get("debut")
    result: list[dict[str, Any]] = []
    for e in events:
        if e.get("source") == "entrainement":
            result.append(e)
            continue
        same_day = _same_day(e.get("debut"), training_debut)
        redundant = same_day and (
            e.get("categorie") == "sport" or _looks_like_workout(e.get("titre"))
        )
        if redundant:
            continue
        result.append(e)
    return result
