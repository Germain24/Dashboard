"""Estimation des calories dépensées par séance — CONV 7.

Choix méthodologique (décision Germain 2026-05-20, "le plus précis") :

- **Muscu** : approche tonnage. Pour un set donné,
      kcal_set ≈ K_MUSCU × (reps × poids_kg)
  avec K_MUSCU = 0.05 kcal/kg-rep (valeur calibrée sur la littérature, en
  ordre de grandeur cohérent avec ~3–6 METS pour la musculation). Cette
  formule reflète l'effort réel mieux qu'un MET fixe.

- **Cardio (course à pied)** : formule de Niemann
      kcal_run ≈ 1.036 × poids_corps_kg × distance_km
  (constante consensus pour la course récréative ; précise à ~10 % près).

- **Cardio générique (warmup tapis / corde à sauter)** : approximation MET
  basique
      kcal ≈ MET × poids_corps_kg × heures
  avec MET_WARMUP = 5 (jogging léger / corde à sauter modérée).

Le poids du corps est récupéré opportunément depuis le module Santé
(`MesureSante`, dernier `poids` connu). Si Santé n'est pas dispo ou que le
poids n'est pas connu, on retombe sur une valeur par défaut (70 kg) — pas
parfait mais évite un 500.
"""

from __future__ import annotations

import datetime as dt
from typing import Iterable, Optional

from sqlmodel import Session, select

from app.models.entrainement import CourseCardio, Seance, SetSerie

# Constantes calibrées (cf. docstring)
K_MUSCU_KCAL_PER_KG_REP = 0.05
NIEMANN_RUN_K = 1.036
MET_WARMUP_CARDIO = 5.0
POIDS_CORPS_FALLBACK_KG = 70.0


def _try_get_latest_weight(session: Session, before: dt.date) -> Optional[float]:
    """Récupère la dernière mesure de poids de Santé. None si pas dispo."""
    try:
        from app.models.sante import MesureSante  # type: ignore
    except Exception:
        return None
    stmt = (
        select(MesureSante)
        .where(MesureSante.date <= before)
        .where(MesureSante.poids.isnot(None))
        .order_by(MesureSante.date.desc())
        .limit(1)
    )
    row = session.exec(stmt).first()
    return float(row.poids) if row and row.poids else None


def resolve_poids_corps(
    session: Session,
    *,
    before: Optional[dt.date] = None,
    fallback: float = POIDS_CORPS_FALLBACK_KG,
) -> float:
    """Poids du corps utilisé dans le calcul de calories."""
    before = before or dt.date.today()
    w = _try_get_latest_weight(session, before)
    return w if w is not None else fallback


def kcal_muscu_from_sets(sets: Iterable[SetSerie]) -> float:
    """Calories pour une liste de séries de muscu (tonnage × K)."""
    tonnage = 0.0
    for s in sets:
        reps = int(s.reps or 0)
        poids = float(s.poids_kg or 0.0)
        tonnage += reps * poids
    return round(K_MUSCU_KCAL_PER_KG_REP * tonnage, 1)


def kcal_run_from_course(course: CourseCardio, poids_corps_kg: float) -> float:
    """Calories pour une course (Niemann)."""
    if not course.distance_km or course.distance_km <= 0:
        return 0.0
    return round(NIEMANN_RUN_K * poids_corps_kg * course.distance_km, 1)


def kcal_cardio_warmup(duree_min: float, poids_corps_kg: float) -> float:
    """Calories pour un warmup cardio générique (tapis, corde, ~5 MET)."""
    if duree_min <= 0:
        return 0.0
    heures = duree_min / 60.0
    return round(MET_WARMUP_CARDIO * poids_corps_kg * heures, 1)


def estimate_calories_seance(
    seance: Seance,
    sets: list[SetSerie],
    *,
    courses: Optional[list[CourseCardio]] = None,
    poids_corps_kg: float = POIDS_CORPS_FALLBACK_KG,
) -> dict:
    """Calories totales d'une séance.

    Retourne `{"kcal_muscu": x, "kcal_cardio": y, "total_kcal": x + y}`.

    Si `seance.type == "cardio"` ou s'il n'y a aucune série mais une durée,
    on bascule en mode cardio warmup ; sinon on calcule en muscu.
    """
    kcal_muscu = 0.0
    kcal_cardio = 0.0
    is_cardio = (seance.type or "").lower() == "cardio"
    if sets and not is_cardio:
        kcal_muscu = kcal_muscu_from_sets(sets)
    elif is_cardio and seance.duree_min:
        kcal_cardio = kcal_cardio_warmup(float(seance.duree_min), poids_corps_kg)
    for c in courses or []:
        kcal_cardio += kcal_run_from_course(c, poids_corps_kg)
    return {
        "kcal_muscu": round(kcal_muscu, 1),
        "kcal_cardio": round(kcal_cardio, 1),
        "total_kcal": round(kcal_muscu + kcal_cardio, 1),
    }


def kcal_for_date(
    session: Session,
    date: dt.date,
    *,
    poids_corps_kg: Optional[float] = None,
) -> dict:
    """Total calories brûlées une date donnée (muscu + cardio).

    Format de retour stable pour la CONV nutrition future :
        {"date": ..., "kcal_muscu": ..., "kcal_cardio": ..., "total_kcal": ...}
    """
    from app.services.entrainement.cardio import get_courses_for_date
    from app.services.entrainement.sessions import get_sessions_for_date
    from app.services.entrainement.sets import list_sets_for_seance

    pdc = poids_corps_kg if poids_corps_kg is not None else resolve_poids_corps(
        session, before=date,
    )
    seances = get_sessions_for_date(session, date)
    courses = get_courses_for_date(session, date)

    total_muscu = 0.0
    total_cardio_warmup = 0.0
    for s in seances:
        sets = list_sets_for_seance(session, s.id)
        agg = estimate_calories_seance(s, sets, poids_corps_kg=pdc)
        total_muscu += agg["kcal_muscu"]
        total_cardio_warmup += agg["kcal_cardio"]
    kcal_run = sum(kcal_run_from_course(c, pdc) for c in courses)

    return {
        "date": date,
        "kcal_muscu": round(total_muscu, 1),
        "kcal_cardio": round(total_cardio_warmup + kcal_run, 1),
        "total_kcal": round(total_muscu + total_cardio_warmup + kcal_run, 1),
        "poids_corps_kg": pdc,
    }
