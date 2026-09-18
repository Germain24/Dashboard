"""Helpers partagés entre les sous-routeurs Études (#506)."""
from __future__ import annotations

import datetime as dt

from app.api.etudes.schemas import CoursRead, EvaluationRead
from app.services.etudes import constants as cst
from app.services.etudes import sessions


def enrich_cours(c, db) -> CoursRead:
    """Injecte lettre, points GPA et total minutes dans le schema."""
    r = CoursRead.model_validate(c)
    if c.note_finale is not None:
        r.lettre = cst.note_to_lettre(c.note_finale)
        r.points_gpa = cst.note_to_gpa(c.note_finale)
    r.total_minutes_etude = sessions.total_minutes_par_cours(db, c.id)
    return r


def enrich_eval(ev) -> EvaluationRead:
    r = EvaluationRead.model_validate(ev)
    if ev.date_limite is not None:
        r.jours_restants = (ev.date_limite - dt.date.today()).days
    return r
