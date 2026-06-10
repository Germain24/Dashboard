"""Schémas du module Cuisine (extraits de routes_cuisine.py, #508)."""
from __future__ import annotations

from pydantic import BaseModel


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


class PantryItemIn(BaseModel):
    ingredient: str
    quantite: float
    unite: str
    date_peremption: str | None = None
    rayon: str = "Autre"


class PantryItemPatch(BaseModel):
    ingredient: str | None = None
    quantite: float | None = None
    unite: str | None = None
    date_peremption: str | None = None
    rayon: str | None = None


class NoteIn(BaseModel):
    note: str
