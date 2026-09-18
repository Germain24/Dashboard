"""Routes Livres — package par module (#510). URLs inchangées.

Le module historique `routes_livres.py` a été découpé en sous-routeurs
cohérents : books, annotations (notes + citations + sessions), insights.
Tous sont montés sous le même préfixe `/livres`.
"""
from fastapi import APIRouter

from . import annotations, books, insights

router = APIRouter(tags=["livres"])
router.include_router(books.router)
router.include_router(annotations.router)
router.include_router(insights.router)
