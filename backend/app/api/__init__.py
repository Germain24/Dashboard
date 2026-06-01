"""Routers FastAPI — un router par module métier.

En CONV 1, chaque router est un squelette : pas de logique, juste un
endpoint `GET /<module>/ping` pour vérifier le routing et faire apparaître
le module dans l'OpenAPI.
"""

from fastapi import APIRouter

from app.api import (
    routes_agenda,
    routes_budget,
    routes_cuisine,
    routes_entrainement,
    routes_etudes,
    routes_finance,
    routes_garderobe,
    routes_habitudes,
    routes_health,
    routes_livres,
    routes_notifications,
    routes_robot,
    routes_sante,
    routes_scheduler,
)

api_router = APIRouter()
api_router.include_router(routes_health.router, tags=["health"])
api_router.include_router(routes_finance.router, prefix="/finance", tags=["finance"])
api_router.include_router(routes_garderobe.router, prefix="/garderobe", tags=["garderobe"])
api_router.include_router(routes_sante.router, prefix="/sante", tags=["sante"])
api_router.include_router(routes_agenda.router, prefix="/agenda", tags=["agenda"])
api_router.include_router(routes_etudes.router, prefix="/etudes", tags=["etudes"])
api_router.include_router(routes_entrainement.router, prefix="/entrainement", tags=["entrainement"])
api_router.include_router(routes_budget.router, prefix="/budget", tags=["budget"])
api_router.include_router(routes_cuisine.router, prefix="/cuisine", tags=["cuisine"])
api_router.include_router(routes_habitudes.router, prefix="/habitudes", tags=["habitudes"])
api_router.include_router(routes_livres.router, prefix="/livres", tags=["livres"])
api_router.include_router(routes_robot.router, prefix="/robot", tags=["robot"])
api_router.include_router(routes_scheduler.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(routes_notifications.router, prefix="/notifications", tags=["notifications"])
