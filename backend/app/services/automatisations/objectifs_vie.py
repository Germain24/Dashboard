"""Objectifs de vie inter-modules (#226) + jalons datés (§5.4).

Un objectif de vie (« -5 kg + 2000 $ épargnés en 3 mois ») regroupe plusieurs
sous-objectifs, chacun rattaché à une métrique d'un autre module — c'est ce
`metric` qui fait le « lien vers les modules concernés ». La progression est
**direction-agnostique** : elle marche pour une cible à la hausse (épargne)
comme à la baisse (poids).

Chaque sous-objectif peut porter une `date` (jalon daté) ; le statut dérivé
(à venir / en retard / atteint) se calcule depuis cette date et la progression.
Les objectifs déjà stockés n'ont pas ce champ : ils restent valides et ne
peuvent simplement jamais être « en retard ».

compute_progress et jalon_statut sont purs (testables) ; resolve_metrics lit la
valeur courante de chaque métrique dans son module (best-effort).
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from sqlmodel import Session, select

from app.models.objectifs_vie import LifeGoal

# Métriques résolvables -> label lisible (pour le builder côté UI).
SUPPORTED_METRICS: dict[str, str] = {
    "poids": "Poids (kg)",
    "epargne": "Épargne nette ($)",
    "habitudes_pct": "Habitudes (%)",
}


def _parse_jalon_date(value: Any) -> dt.date | None:
    """Date d'un jalon, tolérante : champ absent, vide ou illisible -> None
    (un jalon non daté ne peut pas être en retard)."""
    if not value:
        return None
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        return None


def jalon_statut(atteint: bool, date: dt.date | None, today: dt.date) -> str:
    """Statut dérivé d'un jalon : atteint | en_retard | a_venir.

    L'échéance du jour n'est pas encore un retard (la journée n'est pas finie).
    """
    if atteint:
        return "atteint"
    if date is not None and date < today:
        return "en_retard"
    return "a_venir"


def compute_progress(
    objectifs: list[dict[str, Any]], valeurs: dict[str, float],
    *, today: dt.date | None = None,
) -> dict[str, Any]:
    """Progression de chaque sous-objectif + global, et statut de chaque jalon.

    pct = (courant - baseline) / (cible - baseline), borné [0, 1]. Fonctionne
    dans les deux sens : si cible < baseline (perdre du poids), le ratio reste
    positif quand on progresse. None si valeur absente ou baseline == cible.
    """
    today = today or dt.date.today()
    rows: list[dict[str, Any]] = []
    pcts: list[float] = []
    en_retard = 0
    for o in objectifs:
        cur = valeurs.get(o["metric"])
        baseline = float(o["baseline"])
        cible = float(o["cible"])
        if cur is None or cible == baseline:
            pct = None
        else:
            pct = (float(cur) - baseline) / (cible - baseline)
            pct = max(0.0, min(1.0, pct))
        atteint = pct is not None and pct >= 1.0
        date = _parse_jalon_date(o.get("date"))
        statut = jalon_statut(atteint, date, today)
        if statut == "en_retard":
            en_retard += 1
        rows.append({
            **o,
            "courant": cur,
            "pct": None if pct is None else round(pct * 100, 1),
            "atteint": atteint,
            "date": date.isoformat() if date else None,
            "statut": statut,
        })
        if pct is not None:
            pcts.append(pct)
    overall = round(sum(pcts) / len(pcts) * 100, 1) if pcts else None
    return {"objectifs": rows, "pct_global": overall, "jalons_en_retard": en_retard}


def resolve_metrics(session: Session) -> dict[str, float]:
    """Valeur courante de chaque métrique supportée (best-effort, modules absents OK)."""
    vals: dict[str, float] = {}
    try:
        from app.models.sante import MesureSante
        m = session.exec(
            select(MesureSante)
            .where(MesureSante.poids.is_not(None))
            .order_by(MesureSante.date.desc())
        ).first()
        if m and m.poids:
            vals["poids"] = float(m.poids)
    except Exception:
        pass
    try:
        from app.services.budget.transactions import get_transactions
        txs = get_transactions(session, from_date=dt.date(2000, 1, 1), to_date=dt.date.today())
        vals["epargne"] = round(sum(t.montant for t in txs), 2)
    except Exception:
        pass
    try:
        from app.services.habitudes.entries import get_today_checklist
        cl = get_today_checklist(session)
        total = len(cl)
        done = sum(1 for i in cl if i.get("entry") is not None)
        vals["habitudes_pct"] = int(done * 100 / total) if total else 0
    except Exception:
        pass
    return vals


# ─── CRUD ─────────────────────────────────────────────────────────────────────

def create_goal(
    session: Session, *, titre: str, objectifs: list[dict] | None = None,
    echeance: dt.date | None = None,
) -> LifeGoal:
    goal = LifeGoal(titre=titre, echeance=echeance, objectifs=json.dumps(objectifs or []))
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


def list_goals(session: Session) -> list[LifeGoal]:
    return list(session.exec(select(LifeGoal).order_by(LifeGoal.created_at)).all())


def get_goal(session: Session, goal_id: int) -> LifeGoal | None:
    return session.get(LifeGoal, goal_id)


def delete_goal(session: Session, goal_id: int) -> bool:
    goal = session.get(LifeGoal, goal_id)
    if not goal:
        return False
    session.delete(goal)
    session.commit()
    return True


def goal_with_progress(
    session: Session, goal: LifeGoal, *, valeurs: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Représentation d'un objectif + sa progression unifiée."""
    valeurs = valeurs if valeurs is not None else resolve_metrics(session)
    objectifs = json.loads(goal.objectifs)
    prog = compute_progress(objectifs, valeurs)
    return {
        "id": goal.id,
        "titre": goal.titre,
        "echeance": goal.echeance.isoformat() if goal.echeance else None,
        **prog,
    }
