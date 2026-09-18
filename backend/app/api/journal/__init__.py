"""Routes Journal — package par module (#509). URLs inchangées."""
from fastapi import APIRouter

from . import routes

router = APIRouter(tags=["journal"])
router.include_router(routes.router)
