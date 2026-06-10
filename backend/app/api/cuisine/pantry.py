"""Sous-routeur Cuisine : garde-manger (#508, #127)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException

from app.api.cuisine.schemas import PantryItemIn, PantryItemPatch
from app.services.cuisine import pantry as pantry_svc

router = APIRouter()


@router.get("/pantry")
def list_pantry(today: str | None = None):
    ref = today or date.today().isoformat()
    items = pantry_svc.list_items()
    return [
        {**item, "statut": pantry_svc.classify_expiry(item.get("date_peremption"), ref)}
        for item in items
    ]


@router.post("/pantry", status_code=201)
def add_pantry_item(body: PantryItemIn):
    return pantry_svc.add_item(
        body.ingredient, body.quantite, body.unite,
        date_peremption=body.date_peremption, rayon=body.rayon,
    )


@router.patch("/pantry/{item_id}")
def update_pantry_item(item_id: int, body: PantryItemPatch):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    result = pantry_svc.update_item(item_id, patch)
    if result is None:
        raise HTTPException(404, "Article introuvable")
    return result


@router.delete("/pantry/{item_id}", status_code=204)
def delete_pantry_item(item_id: int):
    if not pantry_svc.remove_item(item_id):
        raise HTTPException(404, "Article introuvable")
