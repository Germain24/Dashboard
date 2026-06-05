"""Volume hebdomadaire par groupe musculaire + détection sous/sur-entraînement (#107).

Le volume d'entraînement en hypertrophie se mesure en **séries par groupe
musculaire et par semaine**. Repères usuels (landmarks Renaissance Periodization) :
- MEV (Minimum Effective Volume) ≈ 10 séries/sem : en deçà → sous-entraînement.
- MRV (Maximum Recoverable Volume) ≈ 20 séries/sem : au-delà → sur-entraînement.

Chaque série compte pour chacun des muscles ciblés par son exercice
(`Exercice.muscles`). Fonction de classement pure (`classify_volume`) et
agrégation sur une fenêtre glissante de `days` jours.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session, select

from app.models.entrainement import Exercice, Seance, SetSerie

SETS_MEV = 10  # sous ce seuil : sous-entraînement
SETS_MRV = 20  # au-dessus : sur-entraînement


def classify_volume(sets: int) -> str:
    """Classe un volume hebdo (nb de séries) en sous / optimal / sur."""
    if sets < SETS_MEV:
        return "sous"
    if sets > SETS_MRV:
        return "sur"
    return "optimal"


@dataclass
class MuscleVolume:
    muscle: str
    sets: int
    tonnage_kg: float
    status: str  # "sous" | "optimal" | "sur"


def weekly_muscle_volume(
    session: Session, *, days: int = 7, today: Optional[dt.date] = None
) -> list[MuscleVolume]:
    """Agrège les séries par groupe musculaire sur les `days` derniers jours."""
    today = today or dt.date.today()
    since = today - dt.timedelta(days=days - 1)
    cutoff = dt.datetime.combine(since, dt.time.min)
    stmt = (
        select(SetSerie, Exercice)
        .join(Seance, Seance.id == SetSerie.seance_id)
        .join(Exercice, Exercice.id == SetSerie.exercice_id)
        .where(Seance.date >= cutoff)
    )
    agg: dict[str, dict] = {}
    for s, ex in session.exec(stmt).all():
        for muscle in (ex.muscles or []):
            a = agg.setdefault(muscle, {"sets": 0, "tonnage": 0.0})
            a["sets"] += 1
            a["tonnage"] += (s.reps or 0) * (s.poids_kg or 0.0)

    out = [
        MuscleVolume(
            muscle=muscle,
            sets=a["sets"],
            tonnage_kg=round(a["tonnage"], 1),
            status=classify_volume(a["sets"]),
        )
        for muscle, a in agg.items()
    ]
    out.sort(key=lambda mv: mv.sets, reverse=True)
    return out
