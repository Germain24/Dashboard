"""Objectif patrimonial d'investissement (#objectif_patrimoine)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.core.db import get_session
from app.services.settings import get_preferences, set_preferences

router = APIRouter()


def _get_valeur_portefeuille(session: Session) -> float:
    """Valeur totale du portefeuille en EUR (depuis le dernier snapshot)."""
    try:
        from app.services.finance.snapshots import get_latest_snapshot
        snap = get_latest_snapshot(session)
        if snap:
            return float(snap.valeur or 0.0)
    except Exception:
        pass
    return 0.0


def _eur_per_cad(session: Session) -> float:
    """Taux de change CAD→EUR (best-effort depuis le cache fx)."""
    try:
        from app.services.finance.fx import get_rate
        cad_usd = get_rate("CAD", "USD")
        eur_usd = get_rate("EUR", "USD")
        if eur_usd and cad_usd:
            return cad_usd / eur_usd
    except Exception:
        pass
    return 0.68  # fallback approximatif


@router.get("/objectif-patrimoine")
def get_objectif_patrimoine(session: Session = Depends(get_session)):
    """Progression vers l'objectif patrimonial d'investissement."""
    prefs = get_preferences()
    objectif = float(prefs.get("objectif_patrimoine_eur", 300_000))

    valeur_cad = _get_valeur_portefeuille(session)
    taux = _eur_per_cad(session)
    valeur_eur = round(valeur_cad * taux, 2)

    pct = round(valeur_eur / objectif * 100, 1) if objectif > 0 else 0.0
    restant = round(objectif - valeur_eur, 2)

    return {
        "objectif_eur": objectif,
        "valeur_eur": valeur_eur,
        "valeur_cad": round(valeur_cad, 2),
        "taux_cad_eur": taux,
        "progression_pct": pct,
        "restant_eur": max(restant, 0.0),
        "atteint": valeur_eur >= objectif,
    }


class ObjectifPatch(BaseModel):
    objectif_eur: float


@router.post("/objectif-patrimoine")
def set_objectif_patrimoine(body: ObjectifPatch):
    """Met à jour l'objectif d'investissement (en EUR)."""
    set_preferences({"objectif_patrimoine_eur": body.objectif_eur})
    return {"objectif_eur": body.objectif_eur}
