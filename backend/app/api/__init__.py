"""Routers FastAPI — un router par module métier.

En CONV 1, chaque router est un squelette : pas de logique, juste un
endpoint `GET /<module>/ping` pour vérifier le routing et faire apparaître
le module dans l'OpenAPI.
"""

from fastapi import APIRouter

from app.api.agenda import router as agenda_router
from app.api.data import router as data_router
from app.api.budget import router as budget_router
from app.api.cuisine import router as cuisine_router
from app.api.entrainement import router as entrainement_router
from app.api.etudes import router as etudes_router
from app.api.finance import router as finance_router
from app.api.garderobe import router as garderobe_router
from app.api.habitudes import router as habitudes_router
from app.api.health import router as health_router
from app.api.journal import router as journal_router
from app.api.livres import router as livres_router
from app.api.musique import router as musique_router
from app.api.notifications import router as notifications_router
from app.api.sante import router as sante_router
from app.api.scheduler import router as scheduler_router
from app.api.skincare import router as skincare_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
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
api_router.include_router(musique_router, prefix="/musique")
api_router.include_router(scheduler_router, prefix="/jobs")
api_router.include_router(notifications_router, prefix="/notifications")
api_router.include_router(skincare_router, prefix="/skincare")
api_router.include_router(data_router, prefix="/data")
