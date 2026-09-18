"""Estimation fiscale CTO : plus-values et dividendes, PFU vs barème."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.core.db import get_session
from app.services.finance import impots_transactions as svc

router = APIRouter()


@router.get("/impots/calcul")
def get_calcul_impots(
    annee: int = Query(ge=2000, le=2100),
    autres_revenus: float = Query(default=0.0, ge=0),
    parts: float = Query(default=1.0, gt=0, le=20),
    moins_values_anterieures: float = Query(default=0.0, ge=0),
    moins_values_anterieures_annee: int | None = Query(default=None, ge=1990, le=2100),
    dividendes_eligibles_abattement: bool = True,
    broker: str | None = None,
    session: Session = Depends(get_session),
):
    """Plus-values au PMP et dividendes de ``annee``, puis comparaison des
    regimes PFU et bareme progressif.

    `autres_revenus` : revenu imposable du foyer hors gains de cession (0 par
    défaut : cas actuel de l'utilisateur, sans revenu français).
    `moins_values_anterieures` : report de moins-values antérieur au début du
    grand livre des transactions (saisie manuelle, best-effort).
    """
    if moins_values_anterieures_annee is not None:
        age = annee - moins_values_anterieures_annee
        if age < 1 or age > 10:
            raise HTTPException(
                422,
                "L'annee d'origine du report doit preceder l'annee fiscale de 1 a 10 ans.",
            )
    return svc.compute_tax_summary(
        session, annee=annee, autres_revenus=autres_revenus, parts=parts,
        moins_values_anterieures=moins_values_anterieures,
        moins_values_anterieures_annee=moins_values_anterieures_annee,
        dividendes_eligibles_abattement=dividendes_eligibles_abattement,
        broker=broker,
    )


@router.get("/impots/ventes")
def get_ventes_detail(
    annee: int | None = None,
    broker: str | None = None,
    session: Session = Depends(get_session),
):
    """Detail vente par vente au prix moyen pondere (PMP)."""
    return {"ventes": svc.realized_sales_detail(session, broker=broker, annee=annee)}
