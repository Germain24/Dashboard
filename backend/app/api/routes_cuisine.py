from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.cuisine import Recipe, RecipeIngredient, MealPlanEntry, ShoppingListItem
from app.services.cuisine import recipes as recipes_svc
from app.services.cuisine import macros as macros_svc
from app.services.cuisine import meal_plan as plan_svc
from app.services.cuisine import shopping_list as shop_svc
from pydantic import BaseModel

router = APIRouter()


class IngredientIn(BaseModel):
    nom_libre: str
    quantite: float = 0
    unite: str = ""
    aliment_id: int | None = None  # lien catalogue Santé (macros) ; None = texte libre


class RecipeCreate(BaseModel):
    titre: str
    portions: int = 4
    temps_prep: int = 0
    temps_cuisson: int = 0
    instructions: str = ""
    ingredients: list[IngredientIn] = []


class MealPlanPatch(BaseModel):
    recipe_id: int | None = None
    notes: str = ""


class GeneratePlanRequest(BaseModel):
    semaine: str
    cibles: dict = {"calories": 2500, "proteines": 180, "glucides": 300, "lipides": 80}


@router.get("/recipes")
def list_recipes(search: str | None = None, session: Session = Depends(get_session)):
    recs = recipes_svc.get_recipes(session, search)
    out = []
    for r in recs:
        n = len(
            session.exec(
                select(RecipeIngredient).where(RecipeIngredient.recipe_id == r.id)
            ).all()
        )
        out.append({**r.model_dump(), "ingredient_count": n})
    return out


@router.post("/recipes", status_code=201)
def create_recipe(body: RecipeCreate, session: Session = Depends(get_session)):
    return recipes_svc.create_recipe(session, **body.model_dump())


@router.post("/recipes/from-url", status_code=201)
def from_url(url: str, session: Session = Depends(get_session)):
    data = recipes_svc.import_from_url(url)
    if not data:
        raise HTTPException(422, "Impossible de parser la recette depuis cette URL")
    return recipes_svc.create_recipe(session, **data)


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


@router.get("/recipes/{id}/macros")
def recipe_macros(id: int, portions: int = 1, session: Session = Depends(get_session)):
    return macros_svc.get_recipe_macros(session, id, portions)


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
