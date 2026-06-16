"""Budget d'énergie personnelle (#232).

Modélise la capacité du jour (0-120) à partir de l'énergie ressentie (journal)
ajustée par le sommeil, et estime le coût des activités planifiées (agenda) par
catégorie. Permet de voir si la journée tient dans le budget. Modèle simple et
explicable, pas de prétention scientifique.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlmodel import Session, select

# Coût énergétique estimé par heure et par catégorie d'activité.
CAT_COST_PER_H: dict[str, int] = {
    "travail": 12, "cours": 12, "etudes": 12, "études": 12,
    "sport": 15, "focus": 15,
    "rdv": 8, "perso": 6, "autre": 6,
}
DEFAULT_COST_PER_H = 6
DEFAULT_CAPACITY = 60
MAX_CAPACITY = 120


def compute_energy_budget(
    *, energie: float | None = None, activities: list[dict] | None = None,
    sleep_h: float | None = None,
) -> dict[str, Any]:
    """Capacité du jour − coût des activités = énergie restante.

    `energie` : ressenti 0-10 (journal). `sleep_h` : heures de sommeil (bonus/malus).
    `activities` : [{categorie, duree_min}].
    """
    base = round(energie * 10) if energie is not None else DEFAULT_CAPACITY
    sleep_adj = 0
    if sleep_h is not None:
        if sleep_h >= 7:
            sleep_adj = 10
        elif sleep_h < 6:
            sleep_adj = -15
    capacity = max(0, min(MAX_CAPACITY, base + sleep_adj))

    cost = 0.0
    for a in (activities or []):
        per_h = CAT_COST_PER_H.get((a.get("categorie") or "").lower(), DEFAULT_COST_PER_H)
        cost += per_h * (a.get("duree_min", 0) / 60)
    cost = round(cost)

    remaining = capacity - cost
    statut = "dépassé" if remaining < 0 else "serré" if remaining < 20 else "ok"
    return {"capacite": capacity, "cout_prevu": cost, "restant": remaining, "statut": statut}


def daily_energy_budget(session: Session, *, date: dt.date | None = None) -> dict[str, Any]:
    """Budget d'énergie du jour : énergie (journal) + activités (agenda)."""
    date = date or dt.date.today()

    energie: float | None = None
    try:
        from app.models.journal import MoodEntry
        mood = session.exec(select(MoodEntry).where(MoodEntry.date == date)).first()
        if mood and mood.energie is not None:
            energie = float(mood.energie)
    except Exception:
        pass

    activities: list[dict] = []
    try:
        from app.services.agenda.events import list_events_for_window
        events = list_events_for_window(
            session, dt.datetime.combine(date, dt.time.min), dt.datetime.combine(date, dt.time.max)
        )
        for e in events:
            fin = e.fin or (e.debut + dt.timedelta(hours=1))
            duree = max(0, int((fin - e.debut).total_seconds() // 60))
            activities.append({"categorie": e.categorie or "autre", "duree_min": duree})
    except Exception:
        pass

    budget = compute_energy_budget(energie=energie, activities=activities)
    return {"date": date.isoformat(), "energie_ressentie": energie, "n_activites": len(activities), **budget}
