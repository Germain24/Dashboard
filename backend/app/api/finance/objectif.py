"""Objectif patrimonial d'investissement (#objectif_patrimoine)."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.core.db import get_session
from app.services.settings import get_preferences, set_preferences

router = APIRouter()
DEFAULT_JAPAN_DATE = date(2028, 1, 11)


class ObjectifProgression(BaseModel):
    id: Literal["liberte_financiere", "japon"]
    label: str
    objectif_eur: float
    valeur_eur: float
    progression_pct: float
    restant_eur: float
    atteint: bool
    echeance: date | None
    jours_restants: int | None
    epargne_journaliere_eur: float | None


class ObjectifsPatrimoineResponse(BaseModel):
    objectifs: list[ObjectifProgression]


def _stored_date(value: object, fallback: date = DEFAULT_JAPAN_DATE) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return fallback


def _japan_target_for_day(
    *,
    initial_target: float,
    deadline: date,
    reference_date: date,
    today: date | None = None,
) -> float:
    """Réduit linéairement le budget Japon avec le temps restant.

    Exemple : à J-800, 100 % du budget est nécessaire ; à J-799, il en reste
    799/800. Le retrait du jour suivant vaut 1/799 du solde restant, soit
    toujours 1/800 du montant initial.
    """
    calculation_day = today or date.today()
    initial_days = max((deadline - reference_date).days, 0)
    remaining_days = max((deadline - calculation_day).days, 0)
    if initial_days == 0:
        return max(round(initial_target, 2), 0.0)
    ratio = min(remaining_days / initial_days, 1.0)
    return max(round(initial_target * ratio, 2), 0.0)


def _progression(
    *,
    goal_id: Literal["liberte_financiere", "japon"],
    label: str,
    objectif: float,
    valeur: float,
    echeance: date | None,
    aujourdhui: date | None = None,
) -> ObjectifProgression:
    pct = round(valeur / objectif * 100, 1) if objectif > 0 else 0.0
    restant = max(round(objectif - valeur, 2), 0.0)
    jour_calcul = aujourdhui or date.today()
    jours_restants = max((echeance - jour_calcul).days, 0) if echeance else None
    epargne_journaliere = (
        round(restant / jours_restants, 2)
        if jours_restants and objectif > 0 and restant > 0
        else 0.0 if echeance else None
    )
    return ObjectifProgression(
        id=goal_id,
        label=label,
        objectif_eur=objectif,
        valeur_eur=valeur,
        progression_pct=pct,
        restant_eur=restant,
        atteint=objectif > 0 and valeur >= objectif,
        echeance=echeance,
        jours_restants=jours_restants,
        epargne_journaliere_eur=epargne_journaliere,
    )


@router.get("/objectif-patrimoine", response_model=ObjectifsPatrimoineResponse)
def get_objectif_patrimoine(session: Session = Depends(get_session)):
    """Deux objectifs indépendants : liberté financière et projet Japon.

    La liberté financière suit le patrimoine net après emprunts et taxes.
    Le Japon suit uniquement les comptes bancaires, hors investissements.
    """
    from app.services.finance.patrimoine import (
        bank_account_value_eur,
        financial_freedom_value_eur,
    )

    prefs = get_preferences()
    liberte = _progression(
        goal_id="liberte_financiere",
        label="Liberté financière",
        objectif=float(prefs.get("objectif_patrimoine_eur", 300_000)),
        valeur=financial_freedom_value_eur(session),
        echeance=None,
    )
    japon_date = _stored_date(prefs.get("objectif_japon_date", DEFAULT_JAPAN_DATE.isoformat()))
    today = date.today()
    raw_reference = prefs.get("objectif_japon_date_reference")
    if not raw_reference:
        # Migration des objectifs créés avant l'introduction de la décroissance :
        # la valeur enregistrée devient le budget restant de ce jour, une seule fois.
        raw_reference = today.isoformat()
        set_preferences({"objectif_japon_date_reference": raw_reference})
    japon_reference = _stored_date(
        raw_reference,
        fallback=today,
    )
    japon_target = _japan_target_for_day(
        initial_target=float(prefs.get("objectif_japon_eur", 0)),
        deadline=japon_date,
        reference_date=japon_reference,
        today=today,
    )
    japon = _progression(
        goal_id="japon",
        label="Voyage au Japon",
        objectif=japon_target,
        valeur=bank_account_value_eur(session),
        echeance=japon_date,
        aujourdhui=today,
    )
    return ObjectifsPatrimoineResponse(objectifs=[liberte, japon])


class ObjectifPatch(BaseModel):
    id: Literal["liberte_financiere", "japon"] = "liberte_financiere"
    objectif_eur: float = Field(gt=0)
    echeance: date | None = None


@router.post("/objectif-patrimoine", response_model=ObjectifsPatrimoineResponse)
def set_objectif_patrimoine(body: ObjectifPatch, session: Session = Depends(get_session)):
    """Met à jour une carte objectif sans modifier l'autre."""
    if body.id == "liberte_financiere":
        set_preferences({"objectif_patrimoine_eur": body.objectif_eur})
    else:
        patch: dict[str, float | str] = {
            "objectif_japon_eur": body.objectif_eur,
            "objectif_japon_date_reference": date.today().isoformat(),
        }
        if body.echeance is not None:
            patch["objectif_japon_date"] = body.echeance.isoformat()
        set_preferences(patch)
    return get_objectif_patrimoine(session)
