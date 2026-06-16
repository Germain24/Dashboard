"""Routes Objectifs — veille et préparation des projets long terme."""
from fastapi import APIRouter

from . import routes

router = APIRouter(tags=["objectifs"])
router.include_router(routes.router)
