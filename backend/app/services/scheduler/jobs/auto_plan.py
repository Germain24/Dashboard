"""Job hebdomadaire : (re)planifie le cycle via le planificateur unique.

Tourne chaque jour de cuisine (jeudi & dimanche) → le batch cooking et les
autres blocs (sport, études, repas, sommeil) sont reposés chaque semaine,
au lieu d'une seule fois (#).
"""

import datetime as dt


def run(session) -> str:
    from app.services.agenda.auto_plan import commit
    prop, created = commit(session, dt.date.today())
    return f"Cycle replanifié : {created} blocs ({prop.window_start}→{prop.window_end})"
