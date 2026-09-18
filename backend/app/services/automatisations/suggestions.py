"""Suggestions d'automatisation apprises des habitudes (#218).

Heuristique simple et explicable (pas de ML) : on regarde les événements
d'agenda récents et on repère ceux qui reviennent le MÊME jour de semaine sur
plusieurs semaines distinctes. Si le seuil est atteint, on propose de créer un
rappel/routine — « tu fais X presque tous les lundis, automatiser ? ».

La détection est une fonction pure (testable avec des objets simples) ; le
service charge les événements depuis la base.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlmodel import Session, select

from app.core.timeutil import utcnow
from app.models.agenda import Evenement

WEEKDAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def _norm(titre: str) -> str:
    return " ".join((titre or "").lower().split())


def _median(values: list[int]) -> int:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) // 2


def detect_recurring_patterns(
    events: list[Any],
    *,
    now: dt.datetime,
    min_weeks: int = 3,
    lookback_weeks: int = 8,
) -> list[dict]:
    """Repère les (titre, jour de semaine) récurrents sur ≥ min_weeks semaines.

    `events` : objets avec .titre (str), .debut (datetime), .recurrence_id (int|None).
    Les événements déjà récurrents (recurrence_id non nul) ou hors fenêtre sont
    ignorés. Retour : liste de suggestions triées par occurrences décroissantes.
    """
    cutoff = now - dt.timedelta(weeks=lookback_weeks)
    groups: dict[tuple[str, int], dict] = {}
    for e in events:
        if getattr(e, "recurrence_id", None) is not None:
            continue
        d = e.debut
        if d < cutoff or d > now:
            continue
        key = (_norm(e.titre), d.weekday())
        g = groups.setdefault(key, {"weeks": set(), "minutes": [], "titre": e.titre.strip()})
        g["weeks"].add(d.isocalendar()[:2])  # (année ISO, semaine ISO)
        g["minutes"].append(d.hour * 60 + d.minute)

    suggestions: list[dict] = []
    for (_norm_titre, weekday), g in groups.items():
        n_weeks = len(g["weeks"])
        if n_weeks < min_weeks:
            continue
        med = _median(g["minutes"])
        heure = f"{med // 60:02d}:{med % 60:02d}"
        jour = WEEKDAYS_FR[weekday]
        suggestions.append({
            "titre": g["titre"],
            "weekday": weekday,
            "jour": jour,
            "heure": heure,
            "occurrences": n_weeks,
            "message": f"Tu as « {g['titre']} » presque tous les {jour} (≈ {heure}) — automatiser un rappel ?",
        })

    suggestions.sort(key=lambda s: (-s["occurrences"], s["titre"].lower()))
    return suggestions


def suggest_automations(
    session: Session,
    *,
    now: dt.datetime | None = None,
    min_weeks: int = 3,
    lookback_weeks: int = 8,
) -> list[dict]:
    """Charge les événements récents et en déduit des suggestions (#218)."""
    now = now or utcnow()
    cutoff = now - dt.timedelta(weeks=lookback_weeks)
    events = list(session.exec(select(Evenement).where(Evenement.debut >= cutoff)).all())
    return detect_recurring_patterns(
        events, now=now, min_weeks=min_weeks, lookback_weeks=lookback_weeks
    )
