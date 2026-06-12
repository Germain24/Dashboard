"""Jobs d'automatisations (#203 matin, #204 soir, #208 courses, #209 reappro, #211 budget)."""

from __future__ import annotations

import datetime as dt

from app.models.scheduler import Notification
from app.services.automatisations.briefing import build_morning_briefing, build_evening_recap


def run_briefing_matin(session) -> str:
    message = build_morning_briefing(session)
    session.add(Notification(
        source="briefing_matin",
        level="info",
        titre="Briefing matin",
        message=message,
    ))
    session.commit()
    return "briefing matin cree"


def run_recap_soir(session) -> str:
    message = build_evening_recap(session)
    session.add(Notification(
        source="recap_soir",
        level="info",
        titre="Recap du soir",
        message=message,
    ))
    session.commit()
    return "recap soir cree"


def run_courses_check(session) -> str:
    """Vérifie le garde-manger et notifie si des ingrédients sont bas (#208)."""
    from app.services.automatisations.courses import run_courses_check as _check
    n = _check(session)
    return f"{n} ingredient(s) sous le seuil" if n else "garde-manger ok"


def run_skincare_reorder(session) -> str:
    """Vérifie le stock skincare et notifie si des produits sont à racheter (#209)."""
    from app.services.automatisations.reapprovisionnement import run_skincare_reorder_check
    n = run_skincare_reorder_check(session)
    return f"{n} produit(s) a renouveler" if n else "stock skincare ok"


def run_budget_rebalancing(session) -> str:
    """Rééquilibrage budgétaire du mois précédent (#211), lancé en début de mois."""
    from app.services.automatisations.budget_rebalancing import run_monthly_rebalancing
    today = dt.date.today()
    # Rebalancing sur le mois précédent (lancé le 1er du mois)
    if today.month == 1:
        mois = f"{today.year - 1}-12"
    else:
        mois = f"{today.year}-{today.month - 1:02d}"
    suggestions = run_monthly_rebalancing(session, mois=mois)
    return f"{len(suggestions)} suggestion(s) de reequilibrage pour {mois}"
