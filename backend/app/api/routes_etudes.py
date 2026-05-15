"""Router squelette pour le module `etudes` — CONV 1.

Implémentation réelle dans la CONV dédiée. Pour l'instant, juste un `/ping`
pour vérifier que le routing fonctionne et que le module apparaît dans
l'OpenAPI.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
def ping() -> dict:
    return {"module": "etudes", "ready": False, "message": "stub — voir CONV correspondante"}
