"""Routes Langues — japonais (vocab/kanji) & projets internationaux."""
from fastapi import APIRouter

from . import routes

router = APIRouter(tags=["langues"])
router.include_router(routes.router)
