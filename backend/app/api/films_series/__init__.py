"""Routes Films & Séries (#534-541)."""

from fastapi import APIRouter

from . import routes

router = APIRouter(tags=["films-series"])
router.include_router(routes.router)
