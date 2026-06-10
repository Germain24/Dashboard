"""Routes Données — package par module (#513). URLs inchangées."""
from fastapi import APIRouter

from . import routes

router = APIRouter(tags=["data"])
router.include_router(routes.router)
