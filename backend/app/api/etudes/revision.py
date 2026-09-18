"""Sous-routeur Études : fiches de révision espacée (#506, #99)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


class _RevisionCardIn(BaseModel):
    # Nom conservé tel quel : il apparaît dans les components OpenAPI (contrat figé).
    recto: str
    verso: str
    cours_id: Optional[int] = None


@router.get("/revision/cards")
def revision_cards(due_only: bool = Query(False)):
    """Liste les fiches de révision (toutes ou seulement celles dues, #99)."""
    from app.services.etudes import revision
    return revision.due_cards() if due_only else revision.list_cards()


@router.post("/revision/cards", status_code=201)
def revision_add(body: _RevisionCardIn):
    from app.services.etudes import revision
    try:
        return revision.add_card(body.recto, body.verso, body.cours_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/revision/cards/{card_id}/review")
def revision_review(card_id: int, quality: int = Query(..., ge=0, le=5)):
    """Enregistre une révision (qualité 0-5) et replanifie la fiche (#99)."""
    from app.services.etudes import revision
    try:
        return revision.review_card(card_id, quality)
    except KeyError:
        raise HTTPException(404, "Fiche introuvable")


@router.delete("/revision/cards/{card_id}", status_code=204)
def revision_delete(card_id: int):
    from app.services.etudes import revision
    if not revision.delete_card(card_id):
        raise HTTPException(404, "Fiche introuvable")
