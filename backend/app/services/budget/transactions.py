import datetime as dt
import calendar
from sqlmodel import Session, select
from app.models.budget import BudgetTransaction
from app.services.budget.rules import apply_rules_to_transaction


def create_transaction(session: Session, date: dt.date, montant: float, marchand: str,
                       description: str = "", compte: str = "principal",
                       devise: str = "CAD", auto: bool = False) -> BudgetTransaction:
    cat_id = apply_rules_to_transaction(session, f"{marchand} {description}")
    t = BudgetTransaction(date=date, montant=montant, marchand=marchand,
                          description=description, category_id=cat_id,
                          compte=compte, devise=devise, auto=auto)
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def get_transactions(session: Session, from_date: dt.date | None = None,
                     to_date: dt.date | None = None, category_id: int | None = None) -> list[BudgetTransaction]:
    q = select(BudgetTransaction)
    if from_date:
        q = q.where(BudgetTransaction.date >= from_date)
    if to_date:
        q = q.where(BudgetTransaction.date <= to_date)
    if category_id:
        q = q.where(BudgetTransaction.category_id == category_id)
    return session.exec(q.order_by(BudgetTransaction.date.desc())).all()


def get_monthly_summary(session: Session, mois: str) -> dict:
    year, month = int(mois[:4]), int(mois[5:])
    start = dt.date(year, month, 1)
    end = dt.date(year, month, calendar.monthrange(year, month)[1])
    txs = get_transactions(session, from_date=start, to_date=end)
    revenus = sum(t.montant for t in txs if t.montant > 0)
    depenses = sum(t.montant for t in txs if t.montant < 0)
    by_cat: dict[int | None, float] = {}
    for t in txs:
        by_cat[t.category_id] = by_cat.get(t.category_id, 0) + t.montant
    return {"revenus": revenus, "depenses": depenses, "solde": revenus + depenses, "by_category": by_cat}


def get_disposable(session: Session, mois: str) -> float:
    return get_monthly_summary(session, mois)["solde"]
