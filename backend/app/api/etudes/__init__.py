"""Routes Études — package par module (#506). URLs inchangées.

Le module historique `routes_etudes.py` a été découpé en sous-routeurs
cohérents : cours, evaluations, sessions, revision.
Tous sont montés sous le même préfixe `/etudes`.
"""
from fastapi import APIRouter

from . import cours, evaluations, revision, sessions, skills

router = APIRouter(tags=["etudes"])
router.include_router(cours.router)
router.include_router(evaluations.router)
router.include_router(sessions.router)
router.include_router(revision.router)
router.include_router(skills.router)
