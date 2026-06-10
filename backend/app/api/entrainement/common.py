"""Helpers partagés entre les sous-routeurs Entraînement (#505)."""
from __future__ import annotations

from app.api.entrainement.schemas import SeanceRead, SetSerieRead
from app.services.entrainement import session_rpe, session_tonnage


def seance_to_read(s, sets) -> SeanceRead:
    return SeanceRead(
        id=s.id, date=s.date, type=s.type, duree_min=s.duree_min, note=s.note,
        programme_jour_id=s.programme_jour_id, intensite=s.intensite, source=s.source,
        sets=[SetSerieRead.model_validate(st) for st in sets],
        tonnage_kg=session_tonnage(sets),
        rpe_moyen=session_rpe(sets),
    )
