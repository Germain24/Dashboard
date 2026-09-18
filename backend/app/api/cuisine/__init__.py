"""Routes Cuisine — package par module (#508). URLs inchangées.

Le module historique `routes_cuisine.py` a été découpé en sous-routeurs
cohérents : recipes, planning (meal-plan + shopping-list), pantry.
Tous sont montés sous le même préfixe `/cuisine`.
"""
from fastapi import APIRouter

from . import pantry, planning, recipes

router = APIRouter(tags=["cuisine"])
router.include_router(recipes.router)
router.include_router(planning.router)
router.include_router(pantry.router)
