"""Routes Voyage — package (cf. pattern app/api/garderobe)."""
from fastapi import APIRouter

from . import routes

router = APIRouter(tags=["voyage"])
router.include_router(routes.router)
