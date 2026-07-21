"""Génère automatiquement le menu Santé du jour à 06:30."""

import datetime as dt

from sqlmodel import select

from app.models.sante import MesureSante, PlanNutrition


def run(session):
    today = dt.date.today()
    existing = session.exec(
        select(PlanNutrition).where(PlanNutrition.date == today),
    ).first()
    if existing:
        return f"Plan nutrition déjà prêt pour {today}"

    weight = session.exec(
        select(MesureSante)
        .where(MesureSante.date <= today)
        .where(MesureSante.poids.isnot(None))
        .order_by(MesureSante.date.desc())
        .limit(1),
    ).first()
    if weight is None:
        return f"Plan nutrition non généré pour {today} : aucun poids connu"

    # La route contient l'orchestration canonique (Agenda, compensation J-1,
    # Super C + circulaire, optimisation et persistance).
    from app.api.sante.plan import generate_plan
    from app.api.sante.schemas import PlanGenerateRequest

    response = generate_plan(PlanGenerateRequest(date=today), session)
    return (
        f"Plan nutrition généré pour {today} : {len(response.items)} aliments, "
        f"intensité {response.intensite}"
    )
