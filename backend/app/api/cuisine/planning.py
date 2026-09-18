"""Sous-routeur Cuisine : plan de repas + liste de courses (#508)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.cuisine.schemas import GeneratePlanRequest, MealPlanPatch
from app.core.db import get_session
from app.models.cuisine import MealPlanEntry, ShoppingListItem
from app.services.cuisine import meal_plan as plan_svc
from app.services.cuisine import shopping_list as shop_svc

router = APIRouter()


def _cibles_sante_du_jour(session: Session) -> dict:
    """Cibles macros du jour, même source que l'onglet Santé.

    `calculate_daily_targets` renvoie `(base, compensé)` avec des clés
    capitalisées et accentuées ; la cuisine travaille en minuscules sans accent.
    """
    import datetime as dt

    from app.models.sante import MesureSante
    from app.services.sante.targets import calculate_daily_targets

    latest = session.exec(
        select(MesureSante)
        .where(MesureSante.poids.isnot(None))  # type: ignore[attr-defined]
        .order_by(MesureSante.date.desc())  # type: ignore[attr-defined]
    ).first()
    if not latest or not latest.poids:
        raise HTTPException(
            400,
            "Aucun poids connu : renseigne une mesure dans Santé ou fournis des cibles.",
        )
    _, comp = calculate_daily_targets(float(latest.poids), dt.date.today())
    return {
        "calories": comp["Calories"],
        "proteines": comp["Protéines"],
        "glucides": comp["Glucides"],
        "lipides": comp["Lipides"],
    }


@router.get("/meal-plan")
def get_plan(week: str, session: Session = Depends(get_session)):
    return [
        plan_svc.serialize_meal_entry(entry)
        for entry in session.exec(select(MealPlanEntry).where(MealPlanEntry.semaine == week)).all()
    ]


@router.post("/meal-plan/generate")
def generate_plan(body: GeneratePlanRequest, session: Session = Depends(get_session)):
    cibles = body.cibles or _cibles_sante_du_jour(session)
    return [plan_svc.serialize_meal_entry(entry) for entry in plan_svc.generate_meal_plan(session, body.semaine, cibles)]


@router.patch("/meal-plan/{id}")
def update_plan_entry(id: int, body: MealPlanPatch, session: Session = Depends(get_session)):
    e = session.get(MealPlanEntry, id)
    if not e:
        raise HTTPException(404)
    e.recipe_id = body.recipe_id
    e.notes = body.notes
    session.add(e)
    session.commit()
    return e


@router.get("/shopping-list/preview")
def shopping_preview(
    week: str,
    jours: str | None = None,
    session: Session = Depends(get_session),
):
    """Liste de courses calculée (non persistée), scopable sur un sous-ensemble
    de jours (`jours=0,1,2,3`) pour coller au cycle de cuisine."""
    jour_list = [int(x) for x in jours.split(",") if x != ""] if jours else None
    return shop_svc.compute_shopping(session, week, jour_list)


@router.get("/shopping-list")
def get_shopping(week: str, session: Session = Depends(get_session)):
    items = session.exec(select(ShoppingListItem).where(ShoppingListItem.semaine == week)).all()
    if not items:
        items = shop_svc.generate_shopping_list(session, week)
    return items


@router.post("/shopping-list/done")
def shopping_done(week: str, session: Session = Depends(get_session)):
    return shop_svc.mark_done(session, week)


@router.patch("/shopping-list/{id}")
def update_item(id: int, achete: bool, session: Session = Depends(get_session)):
    item = session.get(ShoppingListItem, id)
    if not item:
        raise HTTPException(404)
    item.achete = achete
    session.add(item)
    session.commit()
    return item
