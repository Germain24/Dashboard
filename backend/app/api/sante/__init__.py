"""Routes Santé — package par module (#504). URLs inchangées.

Le module historique `routes_sante.py` (411 lignes) a été découpé en
sous-routeurs cohérents : mesures, wellbeing, nutrition, plan.
Tous sont montés sous le même préfixe `/sante`.
"""
from fastapi import APIRouter

from . import mesures, nutrition, plan, score, wellbeing

router = APIRouter(tags=["sante"])
router.include_router(mesures.router)
router.include_router(wellbeing.router)
router.include_router(nutrition.router)
router.include_router(plan.router)
router.include_router(score.router)
