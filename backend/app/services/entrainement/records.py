"""Records personnels (PR) par exercice — tableau consolidé tous exercices (#282).

Pour chaque exercice ayant au moins une série enregistrée, on calcule sur tout
l'historique : le meilleur 1RM estimé (Epley) et la série qui l'a produit, ainsi
que la charge la plus lourde jamais soulevée. Complète la progression par-exercice
(progression.py) par une vue d'ensemble « records ».
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session, select

from app.models.entrainement import Exercice, Seance, SetSerie
from app.services.entrainement.one_rm import epley_1rm


@dataclass
class ExerciceRecord:
    exercice_id: int
    exercice_nom: str
    best_1rm_kg: float
    best_1rm_reps: int
    best_1rm_poids_kg: float
    best_1rm_date: Optional[dt.date]
    heaviest_kg: float
    heaviest_reps: int
    heaviest_date: Optional[dt.date]
    nb_sets: int


def personal_records(session: Session) -> list[ExerciceRecord]:
    """Records all-time par exercice, triés par meilleur 1RM décroissant."""
    stmt = (
        select(SetSerie, Seance.date, Exercice.nom)
        .join(Seance, Seance.id == SetSerie.seance_id)
        .join(Exercice, Exercice.id == SetSerie.exercice_id)
    )
    # Accumulateur par exercice.
    acc: dict[int, dict] = {}
    for s, seance_date, nom in session.exec(stmt).all():
        date = seance_date.date() if isinstance(seance_date, dt.datetime) else seance_date
        poids = float(s.poids_kg or 0.0)
        reps = int(s.reps or 0)
        e = epley_1rm(poids, reps)
        r = acc.get(s.exercice_id)
        if r is None:
            r = {
                "nom": nom, "best_1rm": 0.0, "best_reps": 0, "best_poids": 0.0,
                "best_date": None, "heaviest": 0.0, "heaviest_reps": 0,
                "heaviest_date": None, "nb": 0,
            }
            acc[s.exercice_id] = r
        r["nb"] += 1
        if e > r["best_1rm"]:
            r.update(best_1rm=e, best_reps=reps, best_poids=poids, best_date=date)
        if poids > r["heaviest"]:
            r.update(heaviest=poids, heaviest_reps=reps, heaviest_date=date)

    records = [
        ExerciceRecord(
            exercice_id=ex_id,
            exercice_nom=r["nom"],
            best_1rm_kg=round(r["best_1rm"], 2),
            best_1rm_reps=r["best_reps"],
            best_1rm_poids_kg=round(r["best_poids"], 2),
            best_1rm_date=r["best_date"],
            heaviest_kg=round(r["heaviest"], 2),
            heaviest_reps=r["heaviest_reps"],
            heaviest_date=r["heaviest_date"],
            nb_sets=r["nb"],
        )
        for ex_id, r in acc.items()
    ]
    records.sort(key=lambda x: x.best_1rm_kg, reverse=True)
    return records
