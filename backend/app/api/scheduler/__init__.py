"""Routes Jobs (scheduler) — package par module (#514). URLs inchangées."""
from fastapi import APIRouter

from . import routes

router = APIRouter(tags=["jobs"])
router.include_router(routes.router)
