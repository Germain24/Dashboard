"""Routes Habitudes — package par module (#501). URLs inchangées."""
from fastapi import APIRouter

from . import routes

router = APIRouter(tags=["habitudes"])
router.include_router(routes.router)
