"""Endpoints de la fenêtre batch-cook (spec §5)."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.api.sante.schemas import (
    CartPlanItem,
    CartPlanResponse,
    FenetreDayPlan,
    FenetreGenerateRequest,
    FenetreScore,
    PlanItem,
    ShoppingItem,
    WindowPlanResponse,
)
from app.core.db import get_session
from app.models.sante import PlanNutrition, WindowPlan
from app.services.sante import fenetre, fenetre_service
from app.services.sante.adonis_pricing import apply_superc_catalog_prices
from app.services.sante.aliments import load_aliments_dataframe

router = APIRouter()


def _day_plans(session: Session, wp: WindowPlan, df) -> list[FenetreDayPlan]:
    days = fenetre.window_days(wp.anchor_date)
    out: list[FenetreDayPlan] = []
    rows = {r.date: r for r in session.exec(
        select(PlanNutrition).where(PlanNutrition.date.in_(days))).all()}
    for d in days:
        r = rows.get(d)
        items: list[PlanItem] = []
        for nom, g in ((r.quantites if r else None) or {}).items():
            if nom not in df.index:
                continue
            row = df.loc[nom]
            u = float(g) / 100.0
            items.append(PlanItem(
                aliment=nom, quantite_g=float(g), quantite_str=f"{float(g):.0f}g",
                calories=float(row["Energie"]) * u, proteines=float(row["Proteines"]) * u,
                lipides=float(row["Lipides"]) * u, glucides=float(row["Glucides"]) * u,
                prix=float(row["Prix"]) * u))
        out.append(FenetreDayPlan(
            date=d, intensite=(r.intensite if r else "none") or "none",
            items=items, totals=(r.totals if r else {}) or {},
            targets=(r.targets if r else {}) or {},
            repas_travail=((wp.score or {}).get("restaurant_meals", {}).get(d.isoformat(), []))))
    return out


def _to_response(session: Session, wp: WindowPlan) -> WindowPlanResponse:
    # Même jour de référence qu'à la génération, sinon les prix relus ici ne
    # correspondraient pas à ceux du plan persisté.
    shopping_day = fenetre.shopping_day_for(wp.anchor_date)
    # `include_reservoir` indispensable ici : un plan peut contenir des aliments
    # du réservoir Super C. Sans eux dans le DataFrame, `_day_plans` les
    # ignorerait en silence (`if nom not in df.index: continue`) et la fenêtre
    # s'afficherait amputée d'une partie de ses aliments.
    df = load_aliments_dataframe(session, include_reservoir=fenetre_service._reservoir_enabled())
    # Le plan est déjà persisté. Seuls ses aliments sont nécessaires pour
    # reconstruire les portions; re-tarifer les centaines d'autres familles
    # rendait GET /current assez lent pour dépasser le timeout du navigateur.
    plan_names = {str(name) for name in (wp.food_set or {})}
    present = [name for name in df.index if str(name) in plan_names]
    df = df.loc[present].copy()
    df, _ = apply_superc_catalog_prices(df, shopping_day)
    s = wp.score or {}
    return WindowPlanResponse(
        anchor_date=wp.anchor_date, shopping_date=shopping_day,
        length=wp.length, poids_used=float(wp.poids_used or 0.0),
        jours=_day_plans(session, wp, df),
        shopping_list=[ShoppingItem(**it) for it in (wp.shopping_list or [])],
        score=FenetreScore(
            couverture_moyenne=float(s.get("couverture_moyenne", 0.0)),
            pct_micros_atteints=float(s.get("pct_micros_atteints", 0.0)),
            equilibre_macros=float(s.get("equilibre_macros", 0.0)),
            equilibre_moyen=float(s.get("equilibre_moyen", 0.0)),
            cout_total=float(s.get("cout_total", 0.0)),
            cout_optimise=float(s.get("cout_optimise", s.get("cout_total", 0.0))),
            cout_a_payer=float(s.get("cout_a_payer", s.get("cout_total", 0.0))),
            ratio=float(s.get("ratio", 0.0)),
            sous_couverts=list(s.get("sous_couverts", []))),
        warning=wp.warning)


@router.post("/fenetre/generate", response_model=WindowPlanResponse)
def generate_fenetre(payload: FenetreGenerateRequest, session: Session = Depends(get_session)):
    try:
        wp = fenetre_service.generate_window(
            session, day=payload.date, poids=payload.poids, force=payload.force,
            refresh_prices=payload.refresh_prices)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return _to_response(session, wp)


@router.post("/fenetre/generate-async", status_code=status.HTTP_202_ACCEPTED)
def start_generate_fenetre(payload: FenetreGenerateRequest):
    """Lance la génération en tâche de fond et rend un `job_id` à interroger.

    L'endpoint synchrone reste disponible ; celui-ci évite de dépendre du délai
    d'attente du client, la génération demandant ~2 min sur le catalogue élargi.
    """
    from app.services.sante.fenetre_job import start_generate

    job, created = start_generate(
        day=payload.date,
        poids=payload.poids,
        force=payload.force,
        refresh_prices=payload.refresh_prices,
    )
    return {**job, "created": created}


@router.get("/fenetre/generate-active")
def active_generate_fenetre():
    from app.services.sante.fenetre_job import get_active_generate

    return get_active_generate()


@router.get("/fenetre/generate/{job_id}")
def generate_fenetre_status(job_id: str):
    from app.services.sante.fenetre_job import get_generate

    job = get_generate(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Génération introuvable.")
    return job


@router.post("/fenetre/generate/{job_id}/stop")
def stop_generate_fenetre(job_id: str):
    from app.services.sante.fenetre_job import request_stop

    job = request_stop(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Génération introuvable.")
    return job


@router.get("/fenetre/current", response_model=WindowPlanResponse)
def current_fenetre(date: Optional[dt.date] = Query(None), session: Session = Depends(get_session)):
    wp = fenetre_service.get_current_window(session, day=date)
    if wp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucune fenêtre pour cette date.")
    return _to_response(session, wp)


def _cart_plan_for_window(wp: WindowPlan) -> tuple[list[dict], float]:
    from app.services.cuisine.store_pricing import load_superc_pricing_items
    from app.services.sante.cart_matcher import cart_plan as build_cart_plan

    cache = load_superc_pricing_items()
    shopping_day = fenetre.shopping_day_for(wp.anchor_date)
    items = build_cart_plan(wp.shopping_list or [], cache, shopping_day=shopping_day)
    total = round(sum((it["prix_estime"] or 0.0) * it["qty"] for it in items), 2)
    return items, total


@router.get("/fenetre/cart-plan", response_model=CartPlanResponse)
def cart_plan_fenetre(date: Optional[dt.date] = Query(None), session: Session = Depends(get_session)):
    """Produits Super C (superc.ca) + quantités pour la liste de courses à acheter
    de la fenêtre courante. Le remplissage réel du panier est fait à la demande via
    Claude-in-Chrome (cart-only)."""
    wp = fenetre_service.get_current_window(session, day=date)
    if wp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucune fenêtre pour cette date.")
    # Les prix ont été vérifiés avant l'optimisation et sont persistés dans le
    # plan. Une lecture du panier ne doit pas relancer un crawl de catalogue.
    items, total = _cart_plan_for_window(wp)
    return CartPlanResponse(
        anchor_date=wp.anchor_date,
        items=[CartPlanItem(**it) for it in items],
        total_estime=total,
    )


@router.post("/fenetre/cart-fill", status_code=status.HTTP_202_ACCEPTED)
def start_cart_fill_fenetre(
    date: Optional[dt.date] = Query(None), session: Session = Depends(get_session)
):
    """Ouvre Chrome et complète le panier en ligne avec le plan de 3/4 jours."""
    wp = fenetre_service.get_current_window(session, day=date)
    if wp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucune fenêtre pour cette date.")
    items, _ = _cart_plan_for_window(wp)
    from app.services.sante.superc_cart import start_cart_fill

    job, created = start_cart_fill(items, wp.anchor_date.isoformat())
    return {**job, "created": created}


@router.get("/fenetre/cart-fill/{job_id}")
def cart_fill_status(job_id: str):
    from app.services.sante.superc_cart import get_cart_fill

    job = get_cart_fill(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Remplissage de panier introuvable.")
    return job
