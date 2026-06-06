import datetime as dt
import calendar
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError
from app.models.budget import BudgetEnvelope, BudgetTransaction


def upsert_envelope(session: Session, category_id: int, mois: str, montant: float) -> BudgetEnvelope:
    existing = session.exec(
        select(BudgetEnvelope).where(BudgetEnvelope.category_id == category_id, BudgetEnvelope.mois == mois)
    ).first()
    if existing:
        existing.montant = montant
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    env = BudgetEnvelope(category_id=category_id, mois=mois, montant=montant)
    try:
        session.add(env)
        session.commit()
        session.refresh(env)
        return env
    except IntegrityError:
        session.rollback()
        return session.exec(
            select(BudgetEnvelope).where(BudgetEnvelope.category_id == category_id, BudgetEnvelope.mois == mois)
        ).first()


WARNING_PCT = 80.0  # proche de la limite
OVER_PCT = 100.0    # dépassée


def classify_envelope(pct: float) -> str:
    """Statut d'une enveloppe selon le % consommé : ok / warning / over (#114)."""
    if pct > OVER_PCT:
        return "over"
    if pct >= WARNING_PCT:
        return "warning"
    return "ok"


def get_envelope_status(session: Session, mois: str) -> list[dict]:
    envelopes = session.exec(select(BudgetEnvelope).where(BudgetEnvelope.mois == mois)).all()
    year, month = int(mois[:4]), int(mois[5:])
    start = dt.date(year, month, 1)
    end = dt.date(year, month, calendar.monthrange(year, month)[1])
    result = []
    for env in envelopes:
        txs = session.exec(
            select(BudgetTransaction).where(
                BudgetTransaction.category_id == env.category_id,
                BudgetTransaction.date >= start,
                BudgetTransaction.date <= end,
                BudgetTransaction.montant < 0
            )
        ).all()
        depense = abs(sum(t.montant for t in txs))
        pct = (depense / env.montant * 100) if env.montant > 0 else 0
        result.append({
            "category_id": env.category_id,
            "budget": env.montant,
            "depense": depense,
            "reste": env.montant - depense,
            "pct": pct,
            "status": classify_envelope(pct),
        })
    return result
