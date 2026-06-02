"""Sous-routeur Finance : rééquilibrage du portefeuille."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.db import get_session
from app.api.schemas_finance import RebalancingDiffOut, RebalancingLineOut
from app.services.finance.rebalancing import compute_rebalancing_diff

router = APIRouter()


@router.get("/rebalancing/diff", response_model=Optional[RebalancingDiffOut])
def rebalancing_diff(session: Session = Depends(get_session)):
    diff = compute_rebalancing_diff(session)
    if diff is None:
        return None
    return RebalancingDiffOut(
        run_id=diff.run_id,
        run_date=diff.run_date,
        valeur_totale_eur=diff.valeur_totale_eur,
        budget_total_eur=diff.budget_total_eur,
        lignes=[RebalancingLineOut(**l.__dict__) for l in diff.lignes],
        n_acheter=diff.n_acheter,
        n_vendre=diff.n_vendre,
        n_conserver=diff.n_conserver,
    )
