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


@router.get("/meal-plan")
def get_plan(week: str, session: Session = Depends(get_session)):
    return session.exec(select(MealPlanEntry).where(MealPlanEntry.semaine == week)).all()


@router.post("/meal-plan/generate")
def generate_plan(body: GeneratePlanRequest, session: Session = Depends(get_session)):
    return plan_svc.generate_meal_plan(session, body.semaine, body.cibles)


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
