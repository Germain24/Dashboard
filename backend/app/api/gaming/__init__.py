"""Routes Gaming — carnet de bord joueur : jeux, objectifs, builds, filtres."""
from fastapi import APIRouter

from . import routes

router = APIRouter(tags=["gaming"])
router.include_router(routes.router)
