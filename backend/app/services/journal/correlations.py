"""Corrélations déterministes humeur ↔ autres modules (#476). Aucune IA."""
from __future__ import annotations

import math


def pearson(xs: list[float], ys: list[float]) -> float | None:
    """Coefficient de Pearson, ou None si < 2 paires ou variance nulle."""
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return None
    return round(cov / math.sqrt(vx * vy), 3)


def interpret(r: float) -> dict:
    a = abs(r)
    force = "forte" if a >= 0.6 else "modérée" if a >= 0.4 else "faible" if a >= 0.2 else "négligeable"
    return {"force": force, "signe": "positif" if r >= 0 else "négatif"}


def correlate_series(source_by_date: dict[str, float], target_by_date: dict[str, float]) -> dict:
    """Corrèle deux séries datées sur l'intersection de leurs dates."""
    dates = sorted(set(source_by_date) & set(target_by_date))
    xs = [source_by_date[d] for d in dates]
    ys = [target_by_date[d] for d in dates]
    r = pearson(xs, ys)
    if r is None:
        return {"r": None, "force": "indéterminée", "signe": "", "n": len(dates)}
    return {"r": r, "n": len(dates), **interpret(r)}


import datetime as dt

from sqlmodel import Session, select


def compute_correlations(session: Session, jours: int = 90) -> dict:
    """Corrèle humeur & énergie avec sommeil, sport, poids, dépenses (lecture seule)."""
    from app.models.journal import MoodEntry
    from app.models.sante import MesureSante
    from app.models.entrainement import Seance
    from app.models.budget import BudgetTransaction

    fin = dt.date.today()
    debut = fin - dt.timedelta(days=jours)

    moods = session.exec(
        select(MoodEntry).where(MoodEntry.date >= debut).where(MoodEntry.date <= fin)
    ).all()
    humeur_by = {str(m.date): float(m.humeur) for m in moods}
    energie_by = {str(m.date): float(m.energie) for m in moods}
    mood_dates = list(humeur_by.keys())

    mesures = session.exec(
        select(MesureSante).where(MesureSante.date >= debut).where(MesureSante.date <= fin)
    ).all()
    sommeil_by = {str(m.date): float((m.extra or {})["sommeil_h"])
                  for m in mesures if (m.extra or {}).get("sommeil_h") is not None}
    poids_by = {str(m.date): float(m.poids) for m in mesures if m.poids is not None}

    seances = session.exec(select(Seance)).all()
    seance_days = {s.date.date().isoformat() for s in seances if debut <= s.date.date() <= fin}
    # Sport = 0/1 sur TOUS les jours d'humeur (variance nécessaire au calcul).
    sport_by = {d: (1.0 if d in seance_days else 0.0) for d in mood_dates}

    txns = session.exec(
        select(BudgetTransaction).where(BudgetTransaction.date >= debut).where(BudgetTransaction.date <= fin)
    ).all()
    depenses_by: dict[str, float] = {}
    for t in txns:
        depenses_by[str(t.date)] = depenses_by.get(str(t.date), 0.0) + float(t.montant)

    targets = {"sommeil": sommeil_by, "sport": sport_by, "poids": poids_by, "depenses": depenses_by}
    correlations = []
    for source_name, source in (("humeur", humeur_by), ("energie", energie_by)):
        for cible, target in targets.items():
            res = correlate_series(source, target)
            correlations.append({"source": source_name, "cible": cible, **res})

    return {"caveat": "corrélation ≠ causalité", "jours": jours, "correlations": correlations}
