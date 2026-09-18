"""Sous-routeur Finance : alertes de marché (seuils de prix) — #265."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.finance import price_alerts as price_alerts_svc

router = APIRouter()


class PriceAlertIn(BaseModel):
    ticker: str
    seuil: float
    direction: str


class PriceAlertPatch(BaseModel):
    ticker: str | None = None
    seuil: float | None = None
    direction: str | None = None
    actif: bool | None = None


@router.get("/alerts")
def list_alerts():
    return price_alerts_svc.list_alerts()


@router.post("/alerts", status_code=201)
def add_alert(body: PriceAlertIn):
    try:
        return price_alerts_svc.add_alert(body.ticker, body.seuil, body.direction)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.patch("/alerts/{alert_id}")
def update_alert(alert_id: int, body: PriceAlertPatch):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    result = price_alerts_svc.update_alert(alert_id, patch)
    if result is None:
        raise HTTPException(404, "Alerte introuvable")
    return result


@router.delete("/alerts/{alert_id}", status_code=204)
def delete_alert(alert_id: int):
    if not price_alerts_svc.remove_alert(alert_id):
        raise HTTPException(404, "Alerte introuvable")


@router.get("/alerts/status")
def alerts_status():
    return price_alerts_svc.alerts_with_status()
