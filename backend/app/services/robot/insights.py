"""Insights proactifs (#160) — règles pures sur des métriques agrégées.

`build_insights` est pur (testable) ; `get_insights` rassemble les métriques
depuis la DB puis applique les règles.
"""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select


def build_insights(metrics: dict) -> list[dict]:
    """Pur : transforme des métriques en liste d'insights {level, message}.

    Métriques attendues (toutes optionnelles) :
      - habits_done, habits_total
      - budget_revenus, budget_depenses (mois en cours)
      - taches_urgentes (nb tâches en retard/aujourd'hui)
    """
    out: list[dict] = []

    done = metrics.get("habits_done")
    total = metrics.get("habits_total")
    if total:
        ratio = done / total
        if ratio < 0.5:
            out.append({"level": "warning",
                        "message": f"Habitudes : seulement {done}/{total} faites aujourd'hui."})
        elif ratio == 1:
            out.append({"level": "success", "message": "Toutes les habitudes du jour sont faites 🎉"})

    rev = metrics.get("budget_revenus")
    dep = metrics.get("budget_depenses")
    if rev is not None and dep is not None and dep > rev and rev >= 0:
        out.append({"level": "alert",
                    "message": f"Budget : dépenses ({dep:.0f}) > revenus ({rev:.0f}) ce mois."})

    urgentes = metrics.get("taches_urgentes")
    if urgentes:
        out.append({"level": "warning",
                    "message": f"{urgentes} tâche(s) urgente(s) à traiter."})

    return out


def gather_metrics(session: Session, *, today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    from app.models.agenda import Tache
    from app.models.budget import BudgetTransaction
    from app.services.habitudes.entries import get_today_checklist

    rows = get_today_checklist(session)
    habits_done = sum(1 for r in rows if r.get("entry"))

    start = today.replace(day=1)
    nxt = (start.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    txs = session.exec(
        select(BudgetTransaction).where(
            BudgetTransaction.date >= start, BudgetTransaction.date < nxt
        )
    ).all()
    revenus = sum(t.montant for t in txs if t.montant > 0)
    depenses = sum(-t.montant for t in txs if t.montant < 0)

    urgentes = len(session.exec(
        select(Tache).where(
            Tache.statut != "done",
            Tache.deadline.is_not(None),
            Tache.deadline <= today,
        )
    ).all())

    return {
        "habits_done": habits_done,
        "habits_total": len(rows),
        "budget_revenus": revenus,
        "budget_depenses": depenses,
        "taches_urgentes": urgentes,
    }


def get_insights(session: Session, *, today: dt.date | None = None) -> list[dict]:
    return build_insights(gather_metrics(session, today=today))
