"""Routes Travail — suivi professionnel (shifts, heures, revenus)."""
from fastapi import APIRouter

from . import routes

router = APIRouter(tags=["travail"])
router.include_router(routes.router)
