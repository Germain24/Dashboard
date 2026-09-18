"""Routes Musique — package par module (#511). URLs inchangées.

Le module historique `routes_musique.py` a été découpé en sous-routeurs
cohérents : bibliotheque (scan + classement + pistes), playlists.
Tous sont montés sous le même préfixe `/musique`.
"""
from fastapi import APIRouter

from . import bibliotheque, playlists

router = APIRouter(tags=["musique"])
router.include_router(bibliotheque.router)
router.include_router(playlists.router)
