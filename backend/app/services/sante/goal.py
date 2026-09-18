"""Helpers singleton autour de NutritionGoal.

Convention : il existe **au plus un** `NutritionGoal` avec `actif=True`. Si
plusieurs : on retourne le plus récent et on log un warning (corruption).
Si zéro : `ensure_active_goal` crée un défaut compatible legacy.
"""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from app.models.sante import NutritionGoal

logger = logging.getLogger(__name__)


def get_active_goal(session: Session) -> NutritionGoal | None:
    """Retourne le goal actif s'il existe, sinon None.

    En cas de doublon `actif=True` (incident), prend le plus récent (id desc).
    """
    stmt = (
        select(NutritionGoal)
        .where(NutritionGoal.actif == True)  # noqa: E712
        .order_by(NutritionGoal.id.desc())
    )
    rows = session.exec(stmt).all()
    if len(rows) > 1:
        logger.warning("Plusieurs NutritionGoal actifs (%d) — on prend le plus récent", len(rows))
    return rows[0] if rows else None


def ensure_active_goal(session: Session) -> NutritionGoal:
    """Retourne le goal actif, en créant un défaut compatible legacy si besoin.

    Le défaut reproduit le comportement de `legacy/sante/logic.py` :
    - +500 kcal sport day, ×1.1 rest day
    - sport_days = lun, mar, mer, ven, sam (5 jours, conformément à la routine
      de Germain).
    """
    goal = get_active_goal(session)
    if goal:
        return goal
    goal = NutritionGoal(
        poids_cible=None,
        body_fat_target_pct=None,
        date_cible=None,
        type="bulk",
        surplus_kcal_sport=500.0,
        rest_factor=1.1,
        sport_days=[0, 1, 2, 4, 5],
        actif=True,
        note="Défaut auto-créé",
    )
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal
