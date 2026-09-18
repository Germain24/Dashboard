"""Génère automatiquement le menu Santé du jour à 06:30.

Les jours de courses/batch-cooking (lundi/mercredi), génère la **fenêtre**
nutrition (3 ou 4 jours) ; les autres jours, le plan du jour (best-effort, no-op
si un plan/une fenêtre couvre déjà la date).

Lundi et mercredi, et non plus lundi et jeudi : le rabais étudiant Super C ne
court que du lundi au mercredi, donc la fenêtre jeu-dim est achetée le mercredi,
la veille de son premier jour. Elle doit donc être PRÊTE le mercredi matin — d'où
la génération de la fenêtre du LENDEMAIN ce jour-là.
"""

import datetime as dt

from sqlmodel import select

from app.models.sante import MesureSante, PlanNutrition, WindowPlan

#: Jours où l'on fait les courses et où l'on cuisine (lundi=0 … dimanche=6).
COURSES_WEEKDAYS = (0, 2)


def run(session):
    today = dt.date.today()

    # Jours de courses (lun/mer) : génère la fenêtre nutrition. Best-effort
    # (jamais fatal) et idempotent — on ne régénère pas si la fenêtre de l'ancre
    # existe déjà (ex. déjà créée à la main via l'API, ou par un run précédent).
    if today.weekday() in COURSES_WEEKDAYS:
        from app.services.sante.fenetre import anchor_for
        # Mercredi, on achète pour la fenêtre qui commence JEUDI : c'est donc
        # l'ancre du lendemain qu'il faut générer, pas celle du jour (qui
        # pointerait sur la fenêtre lun-mer déjà en cours de consommation).
        cible = today + dt.timedelta(days=1) if today.weekday() == 2 else today
        anchor = anchor_for(cible)
        if session.exec(
            select(WindowPlan).where(WindowPlan.anchor_date == anchor)
        ).first():
            return f"Fenêtre nutrition déjà prête pour {anchor}"
        try:
            from app.services.sante.fenetre_service import generate_window
            wp = generate_window(session, day=cible)
            return (
                f"Fenêtre nutrition générée pour {anchor} (courses le {today}, "
                f"{wp.length} j, {len(wp.food_set)} aliments)"
            )
        except Exception as exc:  # jamais fatal
            return f"Fenêtre nutrition non générée pour {anchor} : {exc}"

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
