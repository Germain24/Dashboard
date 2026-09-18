"""Routes Documents/Administratif (#548)."""

from fastapi import APIRouter

from . import routes

router = APIRouter(tags=["documents"])
router.include_router(routes.router)
