"""Routes Skincare — package par module (#512). URLs inchangées."""
from fastapi import APIRouter

from . import routes

router = APIRouter(tags=["skincare"])
router.include_router(routes.router)
