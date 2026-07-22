"""Objectif patrimonial d'investissement (#objectif_patrimoine)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from app.core.db import get_session
from app.services.settings import get_preferences, set_preferences

router = APIRouter()


@router.get("/objectif-patrimoine")
def get_objectif_patrimoine(session: Session = Depends(get_session)):  # noqa: B008
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


def compute_objectif_japon(
    *,
    liquidites_cad: float,
    date_cible: dt.date,
    budget_quotidien_cad: float,
    today: dt.date | None = None,
    n_comptes: int = 0,
) -> dict:
    """Calcule la réserve décroissante nécessaire jusqu'à la date cible."""
    today = today or dt.date.today()
    # « Jusqu'au » inclut la journée cible : le jour même, il reste encore une
    # journée de budget. À partir du lendemain seulement, la cible tombe à zéro.
    jours_restants = max((date_cible - today).days + 1, 0)
    objectif = round(jours_restants * budget_quotidien_cad, 2)
    ecart = round(liquidites_cad - objectif, 2)
    progression = (
        100.0 if objectif <= 0 else round(liquidites_cad / objectif * 100, 1)
    )
    return {
        "date_cible": date_cible.isoformat(),
        "budget_quotidien_cad": round(budget_quotidien_cad, 2),
        "jours_restants": jours_restants,
        "objectif_restant_cad": objectif,
        "liquidites_cad": round(liquidites_cad, 2),
        "ecart_cad": ecart,
        "progression_pct": progression,
        "atteint": liquidites_cad >= objectif,
        "n_comptes": n_comptes,
    }


@router.get("/objectif-japon")
def get_objectif_japon(session: Session = Depends(get_session)):  # noqa: B008
    """Réserve bancaire cible : budget quotidien CAD × jours restants."""
    from app.services.finance.patrimoine import bank_value_cad

    prefs = get_preferences()
    try:
        date_cible = dt.date.fromisoformat(str(prefs["objectif_japon_date_cible"]))
    except (KeyError, TypeError, ValueError):
        date_cible = dt.date(2028, 9, 1)
    budget = float(prefs.get("objectif_japon_budget_quotidien_cad", 65.0))
    liquidites, n_comptes = bank_value_cad(session)
    return compute_objectif_japon(
        liquidites_cad=liquidites,
        date_cible=date_cible,
        budget_quotidien_cad=budget,
        n_comptes=n_comptes,
    )


class ObjectifJaponPatch(BaseModel):
    date_cible: dt.date
    budget_quotidien_cad: float = Field(gt=0, le=10_000)

    @field_validator("date_cible")
    @classmethod
    def date_cible_doit_etre_future(cls, value: dt.date) -> dt.date:
        if value <= dt.date.today():
            raise ValueError("La date cible doit être postérieure à aujourd'hui")
        return value


@router.post("/objectif-japon")
def set_objectif_japon(body: ObjectifJaponPatch):
    """Met à jour l'horizon et le budget quotidien de la réserve Japon."""
    set_preferences({
        "objectif_japon_date_cible": body.date_cible.isoformat(),
        "objectif_japon_budget_quotidien_cad": body.budget_quotidien_cad,
    })
    return {
        "date_cible": body.date_cible.isoformat(),
        "budget_quotidien_cad": body.budget_quotidien_cad,
    }
