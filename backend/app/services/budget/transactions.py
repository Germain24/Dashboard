import datetime as dt
import calendar
from sqlmodel import Session, select
from app.core.events import Events, bus
from app.models.budget import BudgetTransaction
from app.services.budget.rules import apply_rules_to_transaction


def create_transaction(session: Session, date: dt.date, montant: float, marchand: str,
                       description: str = "", compte: str = "principal",
                       devise: str = "CAD", auto: bool = False,
                       tags: list | None = None) -> BudgetTransaction:
    cat_id = apply_rules_to_transaction(session, f"{marchand} {description}")
    t = BudgetTransaction(date=date, montant=montant, marchand=marchand,
                          description=description, category_id=cat_id,
                          compte=compte, devise=devise, auto=auto,
                          tags=tags or [])
    session.add(t)
    session.commit()
    session.refresh(t)
    # Point d'émission de référence du bus d'événements (#202) : les
    # automatisations (routines, briefings, anomalies) peuvent s'y abonner.
    bus.emit(
        Events.BUDGET_TRANSACTION_CREATED,
        id=t.id,
        montant=t.montant,
        marchand=t.marchand,
        category_id=t.category_id,
        date=t.date.isoformat(),
    )
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


def _previous_month(mois: str) -> str:
    """'YYYY-MM' du mois précédent."""
    year, month = int(mois[:4]), int(mois[5:7])
    if month == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{month - 1:02d}"


def get_monthly_comparison(session: Session, mois: str) -> dict:
    """Synthèse du mois comparée au mois précédent (#229).

    Renvoie pour revenus/dépenses/solde un objet {current, previous, delta,
    delta_pct, direction} via le helper générique period_over_period.
    """
    from app.core.compare import period_over_period

    prev = _previous_month(mois)
    cur_s = get_monthly_summary(session, mois)
    prev_s = get_monthly_summary(session, prev)
    return {
        "mois": mois,
        "mois_precedent": prev,
        "revenus": period_over_period(cur_s["revenus"], prev_s["revenus"]),
        "depenses": period_over_period(cur_s["depenses"], prev_s["depenses"]),
        "solde": period_over_period(cur_s["solde"], prev_s["solde"]),
    }
