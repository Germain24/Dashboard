"""Routers FastAPI — un router par module métier.

En CONV 1, chaque router est un squelette : pas de logique, juste un
endpoint `GET /<module>/ping` pour vérifier le routing et faire apparaître
le module dans l'OpenAPI.
"""

from fastapi import APIRouter

from app.api import (
    routes_data,
    routes_health,
    routes_musique,
    routes_notifications,
    routes_scheduler,
    routes_skincare,
)
from app.api.agenda import router as agenda_router
from app.api.budget import router as budget_router
from app.api.cuisine import router as cuisine_router
from app.api.entrainement import router as entrainement_router
from app.api.etudes import router as etudes_router
from app.api.finance import router as finance_router
from app.api.garderobe import router as garderobe_router
from app.api.habitudes import router as habitudes_router
from app.api.journal import router as journal_router
from app.api.livres import router as livres_router
from app.api.sante import router as sante_router

api_router = APIRouter()
api_router.include_router(routes_health.router, tags=["health"])
api_router.include_router(finance_router, prefix="/finance", tags=["finance"])
api_router.include_router(garderobe_router, prefix="/garderobe")
api_router.include_router(sante_router, prefix="/sante")
api_router.include_router(agenda_router, prefix="/agenda")
api_router.include_router(etudes_router, prefix="/etudes")
api_router.include_router(entrainement_router, prefix="/entrainement")
api_router.include_router(budget_router, prefix="/budget")
api_router.include_router(cuisine_router, prefix="/cuisine")
api_router.include_router(habitudes_router, prefix="/habitudes")
api_router.include_router(journal_router, prefix="/journal")
api_router.include_router(livres_router, prefix="/livres")
api_router.include_router(routes_musique.router, prefix="/musique", tags=["musique"])
api_router.include_router(routes_scheduler.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(routes_notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(routes_skincare.router, prefix="/skincare", tags=["skincare"])
api_router.include_router(routes_data.router, prefix="/data", tags=["data"])
