"""Routes Agenda — package par module (#502). URLs inchangées.

Le module historique `routes_agenda.py` (487 lignes) a été découpé en
sous-routeurs cohérents : jour, events, recurrences, tasks, planner, sync.
Tous sont montés sous le même préfixe `/agenda`.
"""
from fastapi import APIRouter

from . import events, jour, planner, recurrences, sync, tasks

router = APIRouter(tags=["agenda"])
router.include_router(jour.router)
router.include_router(planner.router)
router.include_router(events.router)
router.include_router(recurrences.router)
router.include_router(tasks.router)
router.include_router(sync.router)
