"""Objectif patrimonial d'investissement (#objectif_patrimoine)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.core.db import get_session
from app.services.settings import get_preferences, set_preferences

router = APIRouter()


@router.get("/objectif-patrimoine")
def get_objectif_patrimoine(session: Session = Depends(get_session)):
    """Progression vers l'objectif patrimonial d'investissement.

    `valeur_eur` = mêmes comptes d'investissement (Trading212, Bourse Direct,
    RealT) que l'onglet Patrimoine (`investment_value_eur`) -- PAS l'ancien
    snapshot de portefeuille `SnapshotPortefeuille`, qui ne reflétait que les
    positions dont les transactions sont suivies dans l'app (ex. Bourse
    Direct saisi à la main, sans historique de transactions -> absent du
    snapshot) et affichait donc un chiffre différent de l'onglet Patrimoine
    pour ce qui est censé être la même chose.
    """
    from app.services.finance.patrimoine import investment_value_eur

    prefs = get_preferences()
    objectif = float(prefs.get("objectif_patrimoine_eur", 300_000))

    valeur_eur = investment_value_eur(session)
    pct = round(valeur_eur / objectif * 100, 1) if objectif > 0 else 0.0
    restant = round(objectif - valeur_eur, 2)

    return {
        "objectif_eur": objectif,
        "valeur_eur": valeur_eur,
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
