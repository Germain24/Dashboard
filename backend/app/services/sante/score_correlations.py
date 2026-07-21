"""Corrélations du score de forme avec des signaux externes (§5.2).

`compute_score` = f(sommeil, sport, nutrition). Corréler le score à ces trois
entrées ne mesurerait que sa propre formule : on ne retient donc que des séries
qui n'y entrent pas (humeur, énergie, poids).

Le calcul de Pearson vient du module journal — même implémentation, mêmes
conventions de sortie (`r`, `n`, `force`, `signe`, caveat).
"""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select

from app.services.journal.correlations import correlate_series

# Entrées de `compute_score` : les corréler au score serait circulaire.
COMPOSANTES_DU_SCORE = ("sommeil", "sport", "nutrition")


def score_correlations(session: Session, jours: int = 90) -> dict:
    """Corrèle le score quotidien avec humeur, énergie et poids (lecture seule)."""
    from app.models.journal import MoodEntry
    from app.models.sante import MesureSante
    from app.services.sante.score import score_history

    fin = dt.date.today()
    debut = fin - dt.timedelta(days=jours)

    score_by = {p["date"]: float(p["score"]) for p in score_history(session, days=jours)}

    moods = session.exec(
        select(MoodEntry).where(MoodEntry.date >= debut).where(MoodEntry.date <= fin)
    ).all()
    humeur_by = {str(m.date): float(m.humeur) for m in moods}
    energie_by = {str(m.date): float(m.energie) for m in moods}

    mesures = session.exec(
        select(MesureSante).where(MesureSante.date >= debut).where(MesureSante.date <= fin)
    ).all()
    poids_by = {str(m.date): float(m.poids) for m in mesures if m.poids is not None}

    cibles = {"humeur": humeur_by, "energie": energie_by, "poids": poids_by}
    correlations = [
        {"source": "score", "cible": nom, **correlate_series(score_by, serie)}
        for nom, serie in cibles.items()
    ]

    return {
        "caveat": "corrélation ≠ causalité",
        "jours": jours,
        "exclus": list(COMPOSANTES_DU_SCORE),
        "correlations": correlations,
    }
