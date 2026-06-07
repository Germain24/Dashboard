import datetime as dt
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.budget import BudgetCategory, BudgetRule, BudgetTransaction, BudgetEnvelope
from app.services.budget import categories as cat_svc
from app.services.budget import rules as rules_svc
from app.services.budget import transactions as tx_svc
from app.services.budget import envelopes as env_svc
from app.services.budget import imports as import_svc
from app.services.budget import analytics as analytics_svc
from pydantic import BaseModel

router = APIRouter()


class TransactionCreate(BaseModel):
    date: dt.date
    montant: float
    marchand: str
    description: str = ""
    compte: str = "principal"
    devise: str = "CAD"


class CategoryCreate(BaseModel):
    nom: str
    parent_id: int | None = None
    couleur: str = "#6366f1"


class RuleCreate(BaseModel):
    pattern: str
    category_id: int
    priorite: int = 0


class EnvelopeCreate(BaseModel):
    category_id: int
    mois: str
    montant: float


@router.get("/transactions")
def list_transactions(from_date: dt.date | None = None, to_date: dt.date | None = None,
                      category_id: int | None = None, session: Session = Depends(get_session)):
    return tx_svc.get_transactions(session, from_date, to_date, category_id)


@router.post("/transactions", status_code=201)
def create_transaction(body: TransactionCreate, session: Session = Depends(get_session)):
    return tx_svc.create_transaction(session, **body.model_dump())


@router.patch("/transactions/{id}")
def update_transaction(id: int, category_id: int, session: Session = Depends(get_session)):
    t = session.get(BudgetTransaction, id)
    if not t:
        raise HTTPException(404)
    t.category_id = category_id
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


@router.delete("/transactions/{id}", status_code=204)
def delete_transaction(id: int, session: Session = Depends(get_session)):
    t = session.get(BudgetTransaction, id)
    if not t:
        raise HTTPException(404)
    session.delete(t)
    session.commit()


@router.post("/import")
async def import_csv(file: UploadFile = File(...), compte: str = "principal",
                     session: Session = Depends(get_session)):
    content = (await file.read()).decode("utf-8", errors="replace")
    return import_svc.import_csv(session, content, compte)


@router.get("/categories")
def list_categories(session: Session = Depends(get_session)):
    return cat_svc.get_categories(session)


@router.post("/categories", status_code=201)
def create_category(body: CategoryCreate, session: Session = Depends(get_session)):
    return cat_svc.create_category(session, **body.model_dump())


@router.get("/rules")
def list_rules(session: Session = Depends(get_session)):
    return session.exec(select(BudgetRule)).all()


@router.post("/rules", status_code=201)
def create_rule(body: RuleCreate, session: Session = Depends(get_session)):
    rule = BudgetRule(**body.model_dump())
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.delete("/rules/{id}", status_code=204)
def delete_rule(id: int, session: Session = Depends(get_session)):
    r = session.get(BudgetRule, id)
    if not r:
        raise HTTPException(404)
    session.delete(r)
    session.commit()


@router.post("/rules/apply")
def apply_rules(session: Session = Depends(get_session)):
    return {"updated": rules_svc.reapply_all_rules(session)}


@router.get("/envelopes")
def list_envelopes(month: str, session: Session = Depends(get_session)):
    return env_svc.get_envelope_status(session, month)


@router.post("/envelopes", status_code=201)
def create_envelope(body: EnvelopeCreate, session: Session = Depends(get_session)):
    return env_svc.upsert_envelope(session, body.category_id, body.mois, body.montant)


@router.get("/summary")
def monthly_summary(month: str, session: Session = Depends(get_session)):
    return tx_svc.get_monthly_summary(session, month)


@router.get("/disposable")
def disposable(month: str, session: Session = Depends(get_session)):
    return {"mois": month, "disposable": tx_svc.get_disposable(session, month)}


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


@router.get("/recurring")
def recurring(session: Session = Depends(get_session)):
    """Dépenses récurrentes (abonnements) détectées : même marchand, montant stable, cadence mensuelle (#116)."""
    return analytics_svc.recurring_expenses(session)


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
