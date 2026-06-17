"""Sous-routeur Budget : synthèses, tendances, épargne, export (#507)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.db import get_session
from app.services.budget import analytics as analytics_svc
from app.services.budget import transactions as tx_svc

router = APIRouter()


@router.get("/summary")
def monthly_summary(month: str, session: Session = Depends(get_session)):
    return tx_svc.get_monthly_summary(session, month)


@router.get("/disposable")
def disposable(month: str, session: Session = Depends(get_session)):
    return {"mois": month, "disposable": tx_svc.get_disposable(session, month)}


@router.get("/summary/compare")
def monthly_summary_compare(month: str, session: Session = Depends(get_session)):
    """Synthèse du mois vs mois précédent (revenus/dépenses/solde + deltas) (#229)."""
    return tx_svc.get_monthly_comparison(session, month)


@router.get("/cashflow")
def cashflow(from_date: dt.date, to_date: dt.date, session: Session = Depends(get_session)):
    txs = tx_svc.get_transactions(session, from_date, to_date)
    by_month: dict[str, dict] = {}
    for t in txs:
        key = t.date.strftime("%Y-%m")
        if key not in by_month:
            by_month[key] = {"revenus": 0.0, "depenses": 0.0}
        if t.montant > 0:
            by_month[key]["revenus"] += t.montant
        else:
            by_month[key]["depenses"] += t.montant
    return [{"mois": k, **v} for k, v in sorted(by_month.items())]


@router.get("/by-category")
def by_category(month: str, session: Session = Depends(get_session)):
    """Dépenses du mois par catégorie (nom + couleur + montant + %), pour le camembert (#113)."""
    return analytics_svc.spending_by_category(session, month)


@router.get("/trend")
def trend(months: int = 6, session: Session = Depends(get_session)):
    """Tendance mensuelle revenus/dépenses sur les N derniers mois (#113)."""
    return analytics_svc.spending_trend(session, months)


@router.get("/rolling-summary")
def rolling_summary(days: int = 30, session: Session = Depends(get_session)):
    """Revenus/dépenses/solde sur les N derniers jours glissants."""
    return analytics_svc.rolling_summary(session, days=days)


@router.get("/category-share")
def category_share(days: int = 180, window: int = 30, session: Session = Depends(get_session)):
    """Part (%) des catégories de dépenses au fil du temps (fenêtre glissante)."""
    return analytics_svc.category_share_timeseries(session, days=days, window=window)


@router.get("/recurring")
def recurring(session: Session = Depends(get_session)):
    """Dépenses récurrentes (abonnements) détectées : même marchand, montant stable, cadence mensuelle (#116)."""
    return analytics_svc.recurring_expenses(session)


@router.get("/recurring/projection")
def recurring_projection(session: Session = Depends(get_session)):
    """Récurrentes vs ponctuelles + projection annuelle des abonnements (#266)."""
    return analytics_svc.recurring_summary(session)


@router.get("/savings-goal")
def get_savings_goal(session: Session = Depends(get_session)):
    """Objectif d'épargne mensuel + progression contre le solde du mois courant (#121)."""
    from app.services.budget import savings as savings_svc
    mois = dt.date.today().strftime("%Y-%m")
    solde = tx_svc.get_monthly_summary(session, mois)["solde"]
    return savings_svc.savings_progress(savings_svc.get_savings_goal(), solde)


@router.post("/savings-goal")
def set_savings_goal(montant: float, session: Session = Depends(get_session)):
    """Définit l'objectif d'épargne mensuel (#121)."""
    from app.services.budget import savings as savings_svc
    return {"montant": savings_svc.set_savings_goal(montant)}


@router.get("/export/annual")
def export_annual(year: int, session: Session = Depends(get_session)):
    """Export CSV des transactions de l'année pour déclaration/bilan (#122)."""
    from fastapi import Response
    csv_str = analytics_svc.annual_export(session, year)
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="budget-{year}.csv"'},
    )
