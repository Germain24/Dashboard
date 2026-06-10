"""Routes Entraînement — package par module (#505). URLs inchangées.

Le module historique `routes_entrainement.py` (390 lignes) a été découpé en
sous-routeurs cohérents : exercises, program, sessions, cardio, analytics, jour.
Tous sont montés sous le même préfixe `/entrainement`.
"""
from fastapi import APIRouter

from . import analytics, cardio, exercises, jour, program, sessions

router = APIRouter(tags=["entrainement"])
router.include_router(exercises.router)
router.include_router(program.router)
router.include_router(sessions.router)
router.include_router(cardio.router)
router.include_router(analytics.router)
router.include_router(jour.router)
