"""Sous-routeur Santé : favoris, catalogue d'aliments, objectif nutritionnel (#504)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.sante.schemas import AlimentRead, NutritionGoalRead, NutritionGoalUpdate
from app.core.db import get_session
from app.services.sante import ensure_active_goal

router = APIRouter()


@router.get("/favorites")
def get_favorites():
    """Liste des aliments favoris pour saisie rapide (#64)."""
    from app.services.sante.favorites import list_favorites
    return {"favorites": list_favorites()}


@router.post("/favorites")
def add_favorite_route(nom: str):
    """Ajoute un aliment aux favoris."""
    from app.services.sante.favorites import add_favorite
    try:
        return {"favorites": add_favorite(nom)}
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.delete("/favorites")
def remove_favorite_route(nom: str):
    """Retire un aliment des favoris."""
    from app.services.sante.favorites import remove_favorite
    return {"favorites": remove_favorite(nom)}


@router.get("/aliments", response_model=list[AlimentRead])
def list_aliments(session: Session = Depends(get_session)):
    """Liste le catalogue d'aliments lu depuis data/imports/aliments.csv.

    Le CSV est la source de vérité (cf. services/sante/aliments.py). La table
    SQL `aliment` n'est plus consultée par cette route.
    """
    from app.services.sante.aliments import load_aliments_from_csv
    catalog = load_aliments_from_csv()
    # On simule une `AlimentRead` par entrée (id séquentiel arbitraire pour
    # garder la forme `{id, nom, proprietes}` de l'API V1).
    return [
        AlimentRead(id=i, nom=nom, proprietes=props)
        for i, (nom, props) in enumerate(sorted(catalog.items()), start=1)
    ]


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
