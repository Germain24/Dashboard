"""Sous-routeur Cuisine : recettes, macros, favoris & notes (#508)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.cuisine.schemas import NoteIn, RecipeCreate
from app.core.db import get_session
from app.models.cuisine import Recipe, RecipeIngredient
from app.services.cuisine import macros as macros_svc
from app.services.cuisine import recipe_meta as meta_svc
from app.services.cuisine import recipes as recipes_svc

router = APIRouter()


@router.get("/recipes")
def list_recipes(search: str | None = None, ingredient: str | None = None,
                 session: Session = Depends(get_session)):
    recs = recipes_svc.get_recipes(session, search, ingredient)
    out = []
    for r in recs:
        n = len(
            session.exec(
                select(RecipeIngredient).where(RecipeIngredient.recipe_id == r.id)
            ).all()
        )
        out.append({**r.model_dump(), "ingredient_count": n})
    return out


@router.get("/recipes/{id}")
def get_recipe(id: int, session: Session = Depends(get_session)):
    """Une recette + ses ingrédients (détail, pour l'échelle de portions #126)."""
    r = session.get(Recipe, id)
    if not r:
        raise HTTPException(404, "Recette introuvable")
    ings = recipes_svc.get_recipe_ingredients(session, id)
    return {**r.model_dump(), "ingredients": [i.model_dump() for i in ings]}


@router.post("/recipes", status_code=201)
def create_recipe(body: RecipeCreate, session: Session = Depends(get_session)):
    return recipes_svc.create_recipe(session, **body.model_dump())


@router.post("/recipes/from-url", status_code=201)
def from_url(url: str, session: Session = Depends(get_session)):
    data = recipes_svc.import_from_url(url)
    if not data:
        raise HTTPException(422, "Impossible de parser la recette depuis cette URL")
    return recipes_svc.create_recipe(session, **data)


@router.get("/recipes/{id}/macros")
def recipe_macros(id: int, portions: int = 1, session: Session = Depends(get_session)):
    return macros_svc.get_recipe_macros(session, id, portions)


# ── Favoris & notes par recette (#128) ──────────────────────────────────────

@router.get("/favorites")
def list_favorites():
    return meta_svc.get_favorites()


@router.post("/recipes/{recipe_id}/favorite", status_code=200)
def toggle_favorite(recipe_id: int):
    return meta_svc.toggle_favorite(recipe_id)


@router.get("/recipes/{recipe_id}/note")
def get_recipe_note(recipe_id: int):
    return {"note": meta_svc.get_note(recipe_id)}


@router.patch("/recipes/{recipe_id}/note")
def set_recipe_note(recipe_id: int, body: NoteIn):
    return {"note": meta_svc.set_note(recipe_id, body.note)}
