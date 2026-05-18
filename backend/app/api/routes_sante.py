"""Endpoints du module Sante / Nutrition - CONV 3."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.api.schemas_sante import (
    AlimentRead,
    MesureSanteCreate,
    MesureSanteRead,
    MesureSanteUpdate,
    NutritionGoalRead,
    NutritionGoalUpdate,
    PlanGenerateRequest,
    PlanItem,
    PlanPatchRequest,
    PlanResponse,
    ProjectionResponse,
    TargetsResponse,
    WeightTrendOut,
)
from app.core.db import get_session
from app.models.sante import Aliment, MesureSante, NutritionGoal, PlanNutrition
from app.services.sante import (
    calculate_daily_targets,
    default_intensity_for_date,
    ensure_active_goal,
    project_weight_to_target,
)
from app.services.sante.aliments import load_aliments_dataframe
from app.services.sante.optimizer import optimize_nutrition
from app.services.sante.totals import calculate_plan_totals

# CONV 7 : on consomme l'endpoint intensité du module Entraînement. Comme tout
# tourne dans le même process (FastAPI mono-app), on importe directement le
# service plutôt que de faire un round-trip HTTP. En cas de souci côté
# Entraînement (table manquante, erreur), on retombe sur le placeholder
# `default_intensity_for_date` du module Santé — ce fallback est intentionnel
# (cf. PLAN.md note 11 + CONV7_entrainement.md "Conserver default… comme
# fallback si Entraînement est indisponible ou si aucune séance n'est
# planifiée pour la date demandée").
try:
    from app.services.entrainement import compute_intensity_for_date as _entrainement_intensity
except Exception:  # pragma: no cover — défensif
    _entrainement_intensity = None  # type: ignore


def _resolve_intensity(session, date, sport_days) -> str:
    """Intensité officielle pour `date`. Priorise Entraînement, fallback Santé."""
    if _entrainement_intensity is not None:
        try:
            return _entrainement_intensity(session, date, sport_days_fallback=sport_days)
        except Exception:
            pass
    return default_intensity_for_date(date, sport_days)

router = APIRouter()


@router.get("/ping")
def ping() -> dict:
    return {"module": "sante", "ready": True}


def _history_payload(session: Session, limit_days: int = 90):
    cutoff = dt.date.today() - dt.timedelta(days=limit_days)
    stmt = (
        select(PlanNutrition)
        .where(PlanNutrition.date >= cutoff)
        .order_by(PlanNutrition.date.desc())
    )
    return [
        {"date": p.date, "targets": p.targets, "consumed": p.consumed or {}}
        for p in session.exec(stmt).all()
    ]


def _last_known_weight(session: Session, before: dt.date):
    stmt = (
        select(MesureSante)
        .where(MesureSante.date <= before)
        .where(MesureSante.poids.isnot(None))
        .order_by(MesureSante.date.desc())
        .limit(1)
    )
    row = session.exec(stmt).first()
    return float(row.poids) if row else None


def _plan_to_items(quantites, df):
    items = []
    for nom, grammes in quantites.items():
        if nom not in df.index:
            continue
        row = df.loc[nom]
        q_units = float(grammes) / 100.0
        items.append(PlanItem(
            aliment=nom,
            quantite_g=float(grammes),
            quantite_str=f"{float(grammes):.0f}g" if grammes >= 1.0 else f"{float(grammes):.2f}g",
            calories=float(row["Energie"]) * q_units,
            proteines=float(row["Proteines"]) * q_units,
            lipides=float(row["Lipides"]) * q_units,
            glucides=float(row["Glucides"]) * q_units,
            prix=float(row["Prix"]) * q_units,
        ))
    return items


def _plan_to_response(plan, df):
    quantites = plan.quantites or {}
    items = _plan_to_items(quantites, df)
    return PlanResponse(
        date=plan.date,
        poids_used=float(plan.poids_used or 0.0),
        intensite=plan.intensite or "none",
        intensity_was_default=False,
        base_targets=plan.base_targets or {},
        targets=plan.targets or {},
        items=items,
        totals=plan.totals or {},
        consumed=plan.consumed,
        warning=plan.warning,
        budget_max_daily=float((plan.targets or {}).get("Prix_Max", 18.0)),
    )


@router.get("/mesures", response_model=list[MesureSanteRead])
def list_mesures(days: int = Query(180, ge=1, le=3650), session: Session = Depends(get_session)):
    cutoff = dt.date.today() - dt.timedelta(days=days)
    stmt = select(MesureSante).where(MesureSante.date >= cutoff).order_by(MesureSante.date.asc())
    return [MesureSanteRead.model_validate(m) for m in session.exec(stmt).all()]


@router.post("/mesures", response_model=MesureSanteRead, status_code=status.HTTP_201_CREATED)
def upsert_mesure(payload: MesureSanteCreate, session: Session = Depends(get_session)):
    existing = session.exec(select(MesureSante).where(MesureSante.date == payload.date)).first()
    if existing:
        if payload.poids is not None:
            existing.poids = payload.poids
        if payload.photo_url is not None:
            existing.photo_url = payload.photo_url
        if payload.note is not None:
            existing.note = payload.note
        if payload.extra is not None:
            existing.extra = payload.extra
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return MesureSanteRead.model_validate(existing)
    m = MesureSante(**payload.model_dump())
    session.add(m)
    session.commit()
    session.refresh(m)
    return MesureSanteRead.model_validate(m)


@router.patch("/mesures/{date}", response_model=MesureSanteRead)
def update_mesure(date: dt.date, payload: MesureSanteUpdate, session: Session = Depends(get_session)):
    existing = session.exec(select(MesureSante).where(MesureSante.date == date)).first()
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"mesure du {date} introuvable")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(existing, k, v)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return MesureSanteRead.model_validate(existing)


@router.delete("/mesures/{date}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mesure(date: dt.date, session: Session = Depends(get_session)):
    existing = session.exec(select(MesureSante).where(MesureSante.date == date)).first()
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"mesure du {date} introuvable")
    session.delete(existing)
    session.commit()


@router.get("/aliments", response_model=list[AlimentRead])
def list_aliments(session: Session = Depends(get_session)):
    rows = session.exec(select(Aliment).order_by(Aliment.nom)).all()
    return [AlimentRead.model_validate(a) for a in rows]


@router.get("/goal", response_model=NutritionGoalRead)
def get_goal(session: Session = Depends(get_session)):
    goal = ensure_active_goal(session)
    return NutritionGoalRead.model_validate(goal)


@router.patch("/goal", response_model=NutritionGoalRead)
def update_goal(payload: NutritionGoalUpdate, session: Session = Depends(get_session)):
    goal = ensure_active_goal(session)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(goal, k, v)
    goal.updated_at = dt.datetime.utcnow()
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return NutritionGoalRead.model_validate(goal)


@router.get("/targets/today", response_model=TargetsResponse)
def get_targets_today(
    date: Optional[dt.date] = Query(None),
    poids: Optional[float] = Query(None),
    intensity: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    today = date or dt.date.today()
    goal = ensure_active_goal(session)
    if poids is None:
        poids = _last_known_weight(session, before=today)
    if poids is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Aucun poids connu et aucun poids fourni.")
    intensity_was_default = intensity is None
    if intensity is None:
        intensity = _resolve_intensity(session, today, goal.sport_days)
    history = _history_payload(session)
    base, comp = calculate_daily_targets(
        weight=poids, date=today, history=history, intensity=intensity,
        surplus_kcal_sport=goal.surplus_kcal_sport, rest_factor=goal.rest_factor,
        sport_days=goal.sport_days,
    )
    return TargetsResponse(
        date=today, poids=poids, intensity=intensity,
        intensity_was_default=intensity_was_default, base_targets=base, targets=comp,
    )


@router.post("/plan/generate", response_model=PlanResponse)
def generate_plan(payload: PlanGenerateRequest, session: Session = Depends(get_session)):
    today = payload.date or dt.date.today()
    goal = ensure_active_goal(session)
    poids = payload.poids
    if poids is None:
        poids = _last_known_weight(session, before=today)
    if poids is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Aucun poids connu.")
    intensity_was_default = payload.intensity is None
    intensity = payload.intensity or _resolve_intensity(session, today, goal.sport_days)
    history = _history_payload(session)
    base, comp = calculate_daily_targets(
        weight=poids, date=today, history=history, intensity=intensity,
        surplus_kcal_sport=goal.surplus_kcal_sport, rest_factor=goal.rest_factor,
        sport_days=goal.sport_days,
    )
    df = load_aliments_dataframe(session)
    if df.empty:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Catalogue aliments vide.")
    budget = payload.budget_max_daily if payload.budget_max_daily is not None else comp.get("Prix_Max")
    plan_items, warning = optimize_nutrition(df, comp, budget_max_daily=budget)
    if plan_items is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, warning or "Optimisation impossible")
    quantites = {it["Aliment"]: float(it["Quantite_g"]) for it in plan_items}
    items = _plan_to_items(quantites, df)
    totals = calculate_plan_totals(plan_items, df)
    existing = session.exec(select(PlanNutrition).where(PlanNutrition.date == today)).first()
    if existing:
        existing.poids_used = poids
        existing.intensite = intensity
        existing.base_targets = base
        existing.targets = comp
        existing.quantites = quantites
        existing.totals = totals
        existing.warning = warning
        if payload.force:
            existing.consumed = None
        session.add(existing)
        session.commit()
    else:
        new = PlanNutrition(
            date=today, poids_used=poids, intensite=intensity,
            base_targets=base, targets=comp, quantites=quantites,
            totals=totals, warning=warning,
        )
        session.add(new)
        session.commit()
    # `consumed` is preserved across re-generations unless `force=True`
    consumed_out = None if (payload.force or not existing) else (existing.consumed if existing else None)
    return PlanResponse(
        date=today, poids_used=poids, intensite=intensity,
        intensity_was_default=intensity_was_default,
        base_targets=base, targets=comp, items=items, totals=totals,
        consumed=consumed_out,
        warning=warning or None, budget_max_daily=float(budget or 18.0),
    )


@router.get("/plan/today", response_model=PlanResponse)
def get_plan_today(session: Session = Depends(get_session)):
    return get_plan_for_date(dt.date.today(), session)


@router.get("/plan/{date}", response_model=PlanResponse)
def get_plan_for_date(date: dt.date, session: Session = Depends(get_session)):
    plan = session.exec(select(PlanNutrition).where(PlanNutrition.date == date)).first()
    if not plan:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Aucun plan pour {date}.")
    df = load_aliments_dataframe(session)
    return _plan_to_response(plan, df)


@router.patch("/plan/{date}", response_model=PlanResponse)
def patch_plan(date: dt.date, payload: PlanPatchRequest, session: Session = Depends(get_session)):
    plan = session.exec(select(PlanNutrition).where(PlanNutrition.date == date)).first()
    if not plan:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Aucun plan pour {date}.")
    df = load_aliments_dataframe(session)
    if payload.quantites is not None:
        plan.quantites = payload.quantites
        items_for_total = [{"Aliment": nom, "Quantite_g": grammes} for nom, grammes in payload.quantites.items()]
        plan.totals = calculate_plan_totals(items_for_total, df)
    # consumed_grams (par aliment) → on calcule les totaux nutritionnels et on
    # garde les deux dans `consumed` (clés _g pour les grammes, clés nutriment
    # pour les totaux). La compensation J-1 ne lit que les clés nutriment.
    if payload.consumed_grams is not None:
        items_for_total = [
            {"Aliment": nom, "Quantite_g": grammes}
            for nom, grammes in payload.consumed_grams.items()
            if grammes is not None and grammes > 0
        ]
        nutrit_totals = calculate_plan_totals(items_for_total, df)
        merged: dict = dict(nutrit_totals)
        for nom, grammes in payload.consumed_grams.items():
            merged[f"{nom}_g"] = float(grammes or 0.0)
        plan.consumed = merged
    elif payload.consumed is not None:
        plan.consumed = payload.consumed
    if payload.warning is not None:
        plan.warning = payload.warning
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return _plan_to_response(plan, df)


@router.get("/projection", response_model=ProjectionResponse)
def get_projection(
    target_weight: Optional[float] = Query(None),
    session: Session = Depends(get_session),
):
    goal = ensure_active_goal(session)
    if target_weight is None:
        target_weight = goal.poids_cible
    if target_weight is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Aucun poids cible defini.")
    rows = session.exec(
        select(MesureSante).where(MesureSante.poids.isnot(None)).order_by(MesureSante.date.asc())
    ).all()
    measures = [(m.date, float(m.poids)) for m in rows if m.poids is not None]
    result = project_weight_to_target(measures, target_weight)
    if result is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Aucune mesure de poids disponible.")
    return ProjectionResponse(
        target_weight=result.target_weight,
        current_weight=result.current_weight,
        delta_kg=result.delta_kg,
        days_to_target=result.days_to_target,
        target_date=result.target_date,
        slope_kg_per_week=result.slope_kg_per_week,
        confidence=result.confidence,
        note=result.note,
        trend_7d=WeightTrendOut(**vars(result.trend_7d)) if result.trend_7d else None,
        trend_30d=WeightTrendOut(**vars(result.trend_30d)) if result.trend_30d else None,
    )
