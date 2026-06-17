"""Patrimoine net : actifs manuels (RealT…) + passifs (emprunts)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.core.db import get_session
from app.services.finance import patrimoine as svc

router = APIRouter()


class PatrimoineItemIn(BaseModel):
    type: str  # "actif" | "passif"
    label: str
    valeur: float
    categorie: str = ""
    taux_pct: float | None = None
    mensualite: float | None = None
    devise: str = "EUR"


class PatrimoineItemPatch(BaseModel):
    label: str | None = None
    valeur: float | None = None
    categorie: str | None = None
    taux_pct: float | None = None
    mensualite: float | None = None
    devise: str | None = None


@router.get("/patrimoine")
def get_patrimoine(session: Session = Depends(get_session)):
    """Patrimoine net = actifs manuels − passifs (par défaut), avec le détail.

    Enregistre au passage la photo du jour (idempotente) pour alimenter le
    suivi dans le temps (#257) — utile même sans planificateur actif.
    """
    summary = svc.net_worth_summary(session)
    try:
        svc.record_net_worth_snapshot(session)
    except Exception:
        pass  # best-effort : ne jamais casser la lecture
    return summary


@router.get("/patrimoine/history")
def get_patrimoine_history(days: int = 365, session: Session = Depends(get_session)):
    """Série chronologique du patrimoine net (#257)."""
    return {"days": days, "points": svc.net_worth_history(session, days=days)}


@router.post("/patrimoine", status_code=201)
def create_patrimoine_item(body: PatrimoineItemIn, session: Session = Depends(get_session)):
    try:
        item = svc.create_item(session, **body.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return item.model_dump()


@router.patch("/patrimoine/{item_id}")
def update_patrimoine_item(item_id: int, body: PatrimoineItemPatch, session: Session = Depends(get_session)):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    item = svc.update_item(session, item_id, patch)
    if not item:
        raise HTTPException(404)
    return item.model_dump()


@router.delete("/patrimoine/{item_id}", status_code=204)
def delete_patrimoine_item(item_id: int, session: Session = Depends(get_session)):
    if not svc.delete_item(session, item_id):
        raise HTTPException(404)
