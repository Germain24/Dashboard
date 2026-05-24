"""Suggestion de poids pour un exercice — CONV 7."""

from __future__ import annotations

import datetime as dt
import re
from typing import Optional

from sqlmodel import Session, select

from app.models.entrainement import Exercice, Seance, SetSerie
from app.services.entrainement.calories import resolve_poids_corps

BASELINE_RATIO: dict[str, float] = {
    "developpe couche barre": 0.85,
    "developpe couche halteres": 0.40,
    "developpe incline halteres": 0.35,
    "incline barbell bench press": 0.75,
    "developpe militaire barre": 0.55,
    "dumbbell shoulder press": 0.25,
    "dips lestes": 0.20,
    "rowing barre": 0.70,
    "rowing haltere 1 bras": 0.40,
    "dumbbell row": 0.40,
    "tractions pronation": 0.10,
    "pull-up": 0.0,
    "pull-ups (poids du corps)": 0.0,
    "tirage poulie haute": 0.65,
    "kneeling lat pull-down": 0.55,
    "seated cable row": 0.65,
    "squat barre": 1.20,
    "souleve de terre": 1.50,
    "souleve de terre roumain": 1.20,
    "leg press": 1.80,
    "presse a cuisses": 1.80,
    "hip thrust": 1.30,
    "curl barre": 0.30,
    "curl halteres": 0.15,
    "cable biceps curl": 0.30,
    "elevations laterales": 0.05,
    "lateral raise": 0.05,
    "banded lateral raise": 0.0,
    "extension triceps poulie": 0.25,
    "cable overhead triceps extension": 0.25,
    "dumbbell lying triceps extension": 0.10,
    "face pull": 0.30,
    "shrugs": 0.50,
    "leg curl couche": 0.30,
    "leg extensions": 0.35,
    "leg extension": 0.35,
    "mollets debout": 0.50,
    "seated calf raise": 0.40,
    "ghd back extensions": 0.0,
    "hanging leg raise": 0.0,
}


def _normalize(nom: str) -> str:
    n = nom.lower().strip()
    repl = {"é": "e", "è": "e", "ê": "e", "à": "a", "ô": "o", "î": "i", "ï": "i"}
    for k, v in repl.items():
        n = n.replace(k, v)
    n = re.sub(r"[^a-z0-9\- ]+", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _round_to_increment(weight_kg: float, increment: float = 0.5) -> float:
    if weight_kg <= 0:
        return 0.0
    return round(round(weight_kg / increment) * increment, 2)


def _last_top_set(session: Session, exercice_id: int, *, since: Optional[dt.date] = None) -> Optional[float]:
    cutoff = dt.datetime.combine(since or (dt.date.today() - dt.timedelta(days=180)), dt.time.min)
    stmt = (
        select(SetSerie)
        .join(Seance, Seance.id == SetSerie.seance_id)
        .where(SetSerie.exercice_id == exercice_id)
        .where(Seance.date >= cutoff)
        .order_by(Seance.date.desc())
    )
    rows = session.exec(stmt).all()
    if not rows:
        return None
    return max((float(s.poids_kg or 0.0) for s in rows), default=0.0) or None


# Dict normalisé : on applique _normalize aux clés du dict aussi pour que
# "Pull-ups (poids du corps)" matche après strip des parenthèses.
_BASELINE_RATIO_NORM: dict[str, float] = {}


def _build_normalized_dict():
    if _BASELINE_RATIO_NORM:
        return
    for k, v in BASELINE_RATIO.items():
        _BASELINE_RATIO_NORM[_normalize(k)] = v


def baseline_weight(exercice: Exercice, poids_corps_kg: float, *, default_ratio: float = 0.30) -> Optional[float]:
    _build_normalized_dict()
    key = _normalize(exercice.nom)
    ratio = _BASELINE_RATIO_NORM.get(key, default_ratio)
    if ratio == 0.0:
        return 0.0
    return _round_to_increment(ratio * poids_corps_kg)


def suggested_weight(session: Session, exercice_id: int, *, reps_target: int = 8, poids_corps_kg: Optional[float] = None) -> Optional[float]:
    top = _last_top_set(session, exercice_id)
    if top is not None and top > 0:
        return _round_to_increment(top * 1.025)
    pdc = poids_corps_kg if poids_corps_kg is not None else resolve_poids_corps(session)
    if pdc is None:
        return None
    exercice = session.get(Exercice, exercice_id)
    if exercice is None:
        return None
    return baseline_weight(exercice, pdc)
