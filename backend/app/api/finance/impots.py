"""Calcul de l'impôt sur les plus-values de cession (PFU vs barème progressif)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.db import get_session
from app.services.finance import impots_transactions as svc

router = APIRouter()


@router.get("/impots/calcul")
def get_calcul_impots(
    annee: int,
    autres_revenus: float = 0.0,
    parts: float = 1.0,
    moins_values_anterieures: float = 0.0,
    broker: str | None = None,
    session: Session = Depends(get_session),
):
    """Plus-value réalisée de `annee` (FIFO depuis les transactions), après
    report de moins-values, comparée PFU vs barème progressif.

    `autres_revenus` : revenu imposable du foyer hors gains de cession (0 par
    défaut : cas actuel de l'utilisateur, sans revenu français).
    `moins_values_anterieures` : report de moins-values antérieur au début du
    grand livre des transactions (saisie manuelle, best-effort).
    """
    return svc.compute_tax_summary(
        session, annee=annee, autres_revenus=autres_revenus, parts=parts,
        moins_values_anterieures=moins_values_anterieures, broker=broker,
    )


@router.get("/impots/ventes")
def get_ventes_detail(
    annee: int | None = None,
    broker: str | None = None,
    session: Session = Depends(get_session),
):
    """Détail vente par vente (FIFO) : date, ticker, prix d'achat moyen, prix
    de vente, plus-value, impôt PFU estimé -- pour le tableau détaillé ouvert
    au clic sur les impôts calculés (#annee filtre sur l'année de la vente)."""
    return {"ventes": svc.realized_sales_detail(session, broker=broker, annee=annee)}
