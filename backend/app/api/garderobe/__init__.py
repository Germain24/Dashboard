"""Routes Garde-robe — package par module (#503). URLs inchangées.

Le module historique `routes_garderobe.py` (463 lignes) a été découpé en
sous-routeurs cohérents : vetements, tenues, insights, planner.
Tous sont montés sous le même préfixe `/garderobe`.
"""
from fastapi import APIRouter

from . import insights, objectif, planner, tenues, vetements

router = APIRouter(tags=["garderobe"])
router.include_router(vetements.router)
router.include_router(tenues.router)
router.include_router(insights.router)
router.include_router(planner.router)
router.include_router(objectif.router)
