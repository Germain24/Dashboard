"""Endpoints du module Entraînement — CONV 7."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.api.schemas_entrainement import (
    CaloriesDayResponse,
    CourseCardioCreate,
    CourseCardioRead,
    ExerciceCreate,
    ExerciceRead,
    ExerciceUpdate,
    IntensityResponse,
    OneRMResponse,
    ProgrammeJourRead,
    ProgrammeJourUpdate,
    ProgrammeRead,
    ProgrammeUpdate,
    ProgressionPointOut,
    ProgressionResponse,
    SeanceCreate,
    SeanceRead,
    SeanceUpdate,
    SetSerieCreate,
    SetSerieRead,
    SetSerieUpdate,
    SlotToday,
    TodayResponse,
)
from app.core.db import get_session
from app.services.entrainement import (
    add_set,
    cardio,
    compute_intensity_for_date,
    create_course,
    create_exercice,
    create_session,
    current_1rm,
    delete_session,
    delete_set,
    ensure_active_program,
    ensure_catalogue,
    list_courses,
    list_exercices,
    list_program_days,
    list_sessions,
    list_sets_for_seance,
    pace_sec_per_km,
    progression_for_exercice,
    update_program_day,
)
from app.services.entrainement.exercises import (
    delete_exercice as _delete_exercice,
    get_exercice,
    update_exercice as _update_exercice,
)
from app.services.entrainement.programs import (
    update_program as _update_program,
)
from app.services.entrainement.sessions import (
    get_session_row,
    update_session as _update_session,
)
from app.services.entrainement.sets import update_set as _update_set

router = APIRouter()


@router.get("/ping")
def ping() -> dict:
    return {"module": "entrainement", "ready": True}


# ── Exercices ──
@router.get("/exercises", response_model=list[ExerciceRead])
def list_exercises_endpoint(categorie: Optional[str] = Query(None), session: Session = Depends(get_session)):
    ensure_catalogue(session)
    return [ExerciceRead.model_validate(e) for e in list_exercices(session, categorie)]


@router.post("/exercises", response_model=ExerciceRead, status_code=status.HTTP_201_CREATED)
def create_exercise(payload: ExerciceCreate, session: Session = Depends(get_session)):
    e = create_exercice(
        session, nom=payload.nom, categorie=payload.categorie, muscles=payload.muscles,
        type_mouvement=payload.type_mouvement, unilateral=payload.unilateral,
        source=payload.source, note=payload.note,
    )
    return ExerciceRead.model_validate(e)


@router.patch("/exercises/{exercice_id}", response_model=ExerciceRead)
def patch_exercise(exercice_id: int, payload: ExerciceUpdate, session: Session = Depends(get_session)):
    e = _update_exercice(session, exercice_id, **payload.model_dump(exclude_unset=True))
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "exercice introuvable")
    return ExerciceRead.model_validate(e)


@router.delete("/exercises/{exercice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exercise(exercice_id: int, session: Session = Depends(get_session)):
    if not _delete_exercice(session, exercice_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "exercice introuvable")


# ── Programme ──
def _program_to_read(prog, jours) -> ProgrammeRead:
    return ProgrammeRead(
        id=prog.id, nom=prog.nom, description=prog.description, actif=prog.actif,
        jours=[ProgrammeJourRead.model_validate(j) for j in jours],
    )


@router.get("/program", response_model=ProgrammeRead)
def get_program(session: Session = Depends(get_session)):
    prog = ensure_active_program(session)
    return _program_to_read(prog, list_program_days(session, prog.id))


@router.patch("/program", response_model=ProgrammeRead)
def patch_program(payload: ProgrammeUpdate, session: Session = Depends(get_session)):
    prog = ensure_active_program(session)
    _update_program(session, prog.id, **payload.model_dump(exclude_unset=True))
    return _program_to_read(prog, list_program_days(session, prog.id))


@router.patch("/program/jours/{weekday}", response_model=ProgrammeJourRead)
def patch_program_day(weekday: int, payload: ProgrammeJourUpdate, session: Session = Depends(get_session)):
    if weekday < 0 or weekday > 6:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "weekday doit être 0..6")
    prog = ensure_active_program(session)
    pj = update_program_day(session, prog.id, weekday, label=payload.label, slots=payload.slots)
    if pj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "jour introuvable")
    return ProgrammeJourRead.model_validate(pj)


# ── Séances + séries ──
def _seance_to_read(s, sets) -> SeanceRead:
    return SeanceRead(
        id=s.id, date=s.date, type=s.type, duree_min=s.duree_min, note=s.note,
        programme_jour_id=s.programme_jour_id, intensite=s.intensite, source=s.source,
        sets=[SetSerieRead.model_validate(st) for st in sets],
    )


@router.get("/sessions", response_model=list[SeanceRead])
def list_sessions_endpoint(
    date_from: Optional[dt.date] = Query(None, alias="from"),
    date_to: Optional[dt.date] = Query(None, alias="to"),
    session: Session = Depends(get_session),
):
    rows = list_sessions(session, date_from=date_from, date_to=date_to)
    return [_seance_to_read(s, list_sets_for_seance(session, s.id)) for s in rows]


@router.post("/sessions", response_model=SeanceRead, status_code=status.HTTP_201_CREATED)
def create_session_endpoint(payload: SeanceCreate, session: Session = Depends(get_session)):
    s = create_session(
        session, date=payload.date, type=payload.type, duree_min=payload.duree_min,
        note=payload.note, programme_jour_id=payload.programme_jour_id,
        intensite=payload.intensite, source=payload.source,
    )
    for sp in payload.sets:
        add_set(
            session, seance_id=s.id, exercice_id=sp.exercice_id, reps=sp.reps,
            poids_kg=sp.poids_kg, rpe=sp.rpe, echec=sp.echec, ordre=sp.ordre,
        )
    return _seance_to_read(s, list_sets_for_seance(session, s.id))


@router.get("/sessions/{seance_id}", response_model=SeanceRead)
def get_session_endpoint(seance_id: int, session: Session = Depends(get_session)):
    s = get_session_row(session, seance_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "séance introuvable")
    return _seance_to_read(s, list_sets_for_seance(session, s.id))


@router.patch("/sessions/{seance_id}", response_model=SeanceRead)
def patch_session_endpoint(seance_id: int, payload: SeanceUpdate, session: Session = Depends(get_session)):
    s = _update_session(session, seance_id, **payload.model_dump(exclude_unset=True))
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "séance introuvable")
    return _seance_to_read(s, list_sets_for_seance(session, s.id))


@router.delete("/sessions/{seance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session_endpoint(seance_id: int, session: Session = Depends(get_session)):
    if not delete_session(session, seance_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "séance introuvable")


@router.post("/sessions/{seance_id}/sets", response_model=SetSerieRead, status_code=status.HTTP_201_CREATED)
def add_set_endpoint(seance_id: int, payload: SetSerieCreate, session: Session = Depends(get_session)):
    if get_session_row(session, seance_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "séance introuvable")
    s = add_set(
        session, seance_id=seance_id, exercice_id=payload.exercice_id,
        reps=payload.reps, poids_kg=payload.poids_kg, rpe=payload.rpe,
        echec=payload.echec, ordre=payload.ordre,
    )
    return SetSerieRead.model_validate(s)


@router.patch("/sessions/{seance_id}/sets/{set_id}", response_model=SetSerieRead)
def patch_set_endpoint(seance_id: int, set_id: int, payload: SetSerieUpdate, session: Session = Depends(get_session)):
    s = _update_set(session, set_id, **payload.model_dump(exclude_unset=True))
    if s is None or s.seance_id != seance_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "série introuvable")
    return SetSerieRead.model_validate(s)


@router.delete("/sessions/{seance_id}/sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_set_endpoint(seance_id: int, set_id: int, session: Session = Depends(get_session)):
    if not delete_set(session, set_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "série introuvable")


# ── Progression / 1RM ──
@router.get("/progression/{exercice_id}", response_model=ProgressionResponse)
def get_progression(exercice_id: int, days: int = Query(90, ge=1, le=3650), session: Session = Depends(get_session)):
    e = get_exercice(session, exercice_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "exercice introuvable")
    summary = progression_for_exercice(session, exercice_id, days=days)
    return ProgressionResponse(
        exercice_id=exercice_id, nom=e.nom,
        points=[ProgressionPointOut(**vars(p)) for p in summary.points],
        current_1rm_kg=summary.current_1rm_kg, best_1rm_kg=summary.best_1rm_kg,
        delta_4w_pct=summary.delta_4w_pct,
    )


@router.get("/1rm/{exercice_id}", response_model=OneRMResponse)
def get_one_rm(exercice_id: int, session: Session = Depends(get_session)):
    e = get_exercice(session, exercice_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "exercice introuvable")
    return OneRMResponse(exercice_id=exercice_id, nom=e.nom, current_1rm_kg=current_1rm(session, exercice_id))


# ── Cardio ──
def _course_to_read(c) -> CourseCardioRead:
    return CourseCardioRead(
        id=c.id, date=c.date, distance_km=c.distance_km, duree_sec=c.duree_sec,
        pace_sec_per_km=pace_sec_per_km(c.distance_km, c.duree_sec),
        pace_str=cardio.format_pace(c.distance_km, c.duree_sec),
        note=c.note, source=c.source,
    )


@router.get("/cardio", response_model=list[CourseCardioRead])
def list_cardio(
    date_from: Optional[dt.date] = Query(None, alias="from"),
    date_to: Optional[dt.date] = Query(None, alias="to"),
    session: Session = Depends(get_session),
):
    return [_course_to_read(c) for c in list_courses(session, date_from=date_from, date_to=date_to)]


@router.post("/cardio", response_model=CourseCardioRead, status_code=status.HTTP_201_CREATED)
def post_cardio(payload: CourseCardioCreate, session: Session = Depends(get_session)):
    c = create_course(
        session, date=payload.date, distance_km=payload.distance_km,
        duree_sec=payload.duree_sec, note=payload.note, source=payload.source,
    )
    return _course_to_read(c)


@router.delete("/cardio/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cardio(course_id: int, session: Session = Depends(get_session)):
    if not cardio.delete_course(session, course_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "course introuvable")


# ── Intensité (contrat figé avec Santé) ──
@router.get("/intensity/today", response_model=IntensityResponse)
def intensity_today(session: Session = Depends(get_session)):
    today = dt.date.today()
    return IntensityResponse(date=today, intensity=compute_intensity_for_date(session, today))


@router.get("/intensity/{date}", response_model=IntensityResponse)
def intensity_for_date(date: dt.date, session: Session = Depends(get_session)):
    return IntensityResponse(date=date, intensity=compute_intensity_for_date(session, date))


# ─────────────────────────────────────────────────────────────────────────────
# Seed Garmin (port des programmes Push/Pull/Legs/Upper de Germain)
# ─────────────────────────────────────────────────────────────────────────────

from app.api.schemas_entrainement import GarminSeedRequest, GarminSeedResponse  # noqa: E402
from app.services.entrainement.garmin_seed import seed_garmin_programs  # noqa: E402


@router.post("/program/seed-garmin", response_model=GarminSeedResponse)
def seed_garmin(
    payload: GarminSeedRequest = GarminSeedRequest(),
    session: Session = Depends(get_session),
):
    """Peuple le programme actif avec les 4 séances Garmin de Germain.

    Idempotent : par défaut, n'écrase pas les jours déjà configurés.
    Passe `force=true` pour réinitialiser depuis le dump Garmin.

    Note : samedi (Lower) reste à définir — pas dans le dump Garmin partagé.
    """
    return seed_garmin_programs(session, force=payload.force)


# ─────────────────────────────────────────────────────────────────────────────
# Vue "Aujourd'hui" + calories par date (CONV nutrition future)
# ─────────────────────────────────────────────────────────────────────────────

import re  # noqa: E402

from app.services.entrainement.calories import (  # noqa: E402
    estimate_calories_seance,
    kcal_for_date,
    resolve_poids_corps,
)
from app.services.entrainement.exercises import (  # noqa: E402
    get_exercice_by_nom,
)
from app.services.entrainement.programs import program_day_for_date  # noqa: E402
from app.services.entrainement.suggested_weight import suggested_weight  # noqa: E402

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

    enriched_slots: list[SlotToday] = []
    for s in raw_slots:
        slot_label = str(s.get("label") or "")
        exo = _resolve_slot_exercice(session, slot_label)
        sugg = None
        if exo is not None:
            sugg = suggested_weight(
                session, exo.id,
                reps_target=_reps_target_to_int(s.get("reps_target")),
                poids_corps_kg=pdc,
            )
        enriched_slots.append(SlotToday(
            label=slot_label,
            note=s.get("note"),
            sets_target=s.get("sets_target"),
            reps_target=s.get("reps_target"),
            charge_indicative_kg=s.get("charge_indicative_kg"),
            exercice_id=exo.id if exo else None,
            categorie=exo.categorie if exo else None,
            poids_suggere_kg=sugg,
        ))

    # Séance du jour (la plus récente s'il y en a plusieurs)
    seance_dto = None
    kcal_live = 0.0
    from app.services.entrainement.sessions import get_sessions_for_date
    seances = get_sessions_for_date(session, today)
    if seances:
        s = seances[-1]
        sets = list_sets_for_seance(session, s.id)
        seance_dto = _seance_to_read(s, sets)
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
    )


@router.get("/calories/{date}", response_model=CaloriesDayResponse)
def calories_for_date(date: dt.date, session: Session = Depends(get_session)):
    """Total calories brûlées une date donnée (pour la CONV nutrition future)."""
    agg = kcal_for_date(session, date)
    return CaloriesDayResponse(**agg)
