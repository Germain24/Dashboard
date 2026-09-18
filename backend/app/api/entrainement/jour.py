"""Sous-routeur Entraînement : vue « Aujourd'hui », calories, intensité (#505)."""
from __future__ import annotations

import datetime as dt
import re

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.entrainement.common import seance_to_read
from app.api.entrainement.schemas import (
    CaloriesDayResponse,
    IntensityResponse,
    LastPerfOut,
    MesocycleResponse,
    SlotToday,
    TodayResponse,
)
from app.core.db import get_session
from app.services.entrainement import (
    compute_intensity_for_date,
    ensure_active_program,
    last_performance,
    list_sets_for_seance,
    mesocycle,
)
from app.services.entrainement.calories import (
    estimate_calories_seance,
    kcal_for_date,
    resolve_poids_corps,
)
from app.services.entrainement.exercises import get_exercice_by_nom
from app.services.entrainement.programs import program_day_for_date
from app.services.entrainement.suggested_weight import suggested_weight

router = APIRouter()

_SLOT_CLEAN_RE = re.compile(r"\s*\([^)]*\)\s*")


def _resolve_slot_exercice(session: Session, label: str):
    """Mappe un label de slot Garmin vers un Exercice (best effort).

    Strip les annotations "(warm-up)" / "(bis)" puis match exact sur `nom`.
    """
    nom = _SLOT_CLEAN_RE.sub("", label or "").strip()
    if not nom:
        return None
    return get_exercice_by_nom(session, nom)


def _reps_target_to_int(reps_target) -> int:
    """Best-effort cast pour la suggestion de poids."""
    try:
        return int(reps_target)
    except Exception:
        # "8/4/2/1/5", "5 min", etc. → on prend 8 par défaut
        return 8


@router.get("/today", response_model=TodayResponse)
def today_endpoint(session: Session = Depends(get_session)):
    """Vue opérationnelle de la séance du jour.

    Agrège : programme du jour + slots enrichis (exercice_id + poids
    suggéré), séance déjà créée s'il y en a une, kcal estimées live.
    L'UI doit pouvoir tout afficher avec un seul appel.
    """
    today = dt.date.today()
    prog = ensure_active_program(session)
    pj = program_day_for_date(session, today, programme_id=prog.id)
    pdc = resolve_poids_corps(session, before=today)
    label = pj.label if pj else "Repos"
    raw_slots: list[dict] = list(pj.slots) if pj else []

    meso = mesocycle.current(today=today)

    enriched_slots: list[SlotToday] = []
    for s in raw_slots:
        slot_label = str(s.get("label") or "")
        exo = _resolve_slot_exercice(session, slot_label)
        sugg = None
        last_perf = None
        if exo is not None:
            sugg = suggested_weight(
                session, exo.id,
                reps_target=_reps_target_to_int(s.get("reps_target")),
                poids_corps_kg=pdc,
            )
            lp = last_performance(session, exo.id, before=today)
            if lp is not None:
                last_perf = LastPerfOut(date=lp.date, resume=lp.resume)
        sets_target = s.get("sets_target")
        enriched_slots.append(SlotToday(
            label=slot_label,
            note=s.get("note"),
            sets_target=sets_target,
            reps_target=s.get("reps_target"),
            charge_indicative_kg=s.get("charge_indicative_kg"),
            exercice_id=exo.id if exo else None,
            categorie=exo.categorie if exo else None,
            poids_suggere_kg=sugg,
            derniere_fois=last_perf,
            sets_target_semaine=mesocycle.adjust_sets(sets_target, meso) if meso else None,
        ))

    # Séance du jour (la plus récente s'il y en a plusieurs)
    seance_dto = None
    kcal_live = 0.0
    from app.services.entrainement.sessions import get_sessions_for_date
    seances = get_sessions_for_date(session, today)
    if seances:
        s = seances[-1]
        sets = list_sets_for_seance(session, s.id)
        seance_dto = seance_to_read(s, sets)
        agg = estimate_calories_seance(s, sets, poids_corps_kg=pdc)
        kcal_live = agg["total_kcal"]

    return TodayResponse(
        date=today,
        weekday=today.weekday(),
        jour_label=label,
        programme_jour_id=pj.id if pj else None,
        slots=enriched_slots,
        seance_en_cours=seance_dto,
        kcal_estimees=kcal_live,
        poids_corps_kg=pdc,
        mesocycle=MesocycleResponse(**meso) if meso else None,
    )


@router.get("/calories/{date}", response_model=CaloriesDayResponse)
def calories_for_date(date: dt.date, session: Session = Depends(get_session)):
    """Total calories brûlées une date donnée (pour la CONV nutrition future)."""
    agg = kcal_for_date(session, date)
    return CaloriesDayResponse(**agg)


@router.get("/intensity/today", response_model=IntensityResponse)
def intensity_today(session: Session = Depends(get_session)):
    today = dt.date.today()
    return IntensityResponse(date=today, intensity=compute_intensity_for_date(session, today))


@router.get("/intensity/{date}", response_model=IntensityResponse)
def intensity_for_date(date: dt.date, session: Session = Depends(get_session)):
    return IntensityResponse(date=date, intensity=compute_intensity_for_date(session, date))
