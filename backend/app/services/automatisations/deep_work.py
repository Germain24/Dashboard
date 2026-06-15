"""Planificateur « deep work » (#220).

Réserve automatiquement des blocs de concentration dans les créneaux libres de
la semaine, en **priorisant les jours les moins chargés** (charge agenda/études)
pour ne pas surcharger une journée déjà dense.

`select_deep_work_blocks` est une fonction pure (testable sans base) ;
`plan_deep_work` construit les créneaux depuis l'agenda et persiste (idempotent).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlmodel import Session, select

from app.models.agenda import Evenement
from app.services.agenda.events import list_events_for_window
from app.services.agenda.slots import free_slots

FOCUS_COLOR = "#8B5CF6"
FOCUS_SOURCE = "deep_work"


def _block(debut: dt.datetime, block_min: int) -> dict[str, Any]:
    return {
        "titre": "Deep work",
        "debut": debut,
        "fin": debut + dt.timedelta(minutes=block_min),
        "duree_min": block_min,
        "categorie": "focus",
        "couleur": FOCUS_COLOR,
        "source": FOCUS_SOURCE,
    }


def select_deep_work_blocks(
    days: list[dict[str, Any]],
    *,
    n_blocks: int,
    block_min: int,
    max_per_day: int = 2,
) -> list[dict[str, Any]]:
    """Choisit jusqu'à `n_blocks` blocs de `block_min` minutes.

    `days` : liste de {"load_min": int, "slots": [{"debut", "duree_min"}, ...]}.
    Les jours les MOINS chargés (load_min) sont servis en premier ; au plus
    `max_per_day` blocs par jour ; un bloc par créneau libre (pas de chevauchement,
    les créneaux étant disjoints). Résultat trié par début.
    """
    chosen: list[dict[str, Any]] = []
    for day in sorted(days, key=lambda d: d["load_min"]):
        if len(chosen) >= n_blocks:
            break
        placed = 0
        for slot in day["slots"]:
            if len(chosen) >= n_blocks or placed >= max_per_day:
                break
            if slot["duree_min"] < block_min:
                continue
            chosen.append(_block(slot["debut"], block_min))
            placed += 1
    chosen.sort(key=lambda b: b["debut"])
    return chosen


def plan_deep_work(
    session: Session,
    week_start: dt.date,
    *,
    n_blocks: int = 5,
    block_min: int = 90,
    day_start_h: int = 8,
    day_end_h: int = 20,
    max_per_day: int = 2,
    dry_run: bool = True,
) -> list[dict[str, Any]]:
    """Planifie des blocs deep work sur la semaine selon la charge agenda.

    dry_run=True (défaut) : ne persiste pas, retourne juste les blocs proposés.
    Idempotent : ne recrée pas un bloc deep work au même début.
    """
    # Cible = N blocs deep work AU TOTAL pour la semaine (pas +N par appel).
    # On compte ceux déjà présents et on ne crée que le reste -> idempotent.
    wk_from = dt.datetime.combine(week_start, dt.time(0, 0))
    wk_to = dt.datetime.combine(week_start + dt.timedelta(days=7), dt.time(0, 0))
    existing = session.exec(
        select(Evenement)
        .where(Evenement.source == FOCUS_SOURCE)
        .where(Evenement.debut >= wk_from)
        .where(Evenement.debut < wk_to)
    ).all()
    existing_debuts = {e.debut for e in existing}
    remaining = max(0, n_blocks - len(existing))
    if remaining == 0:
        return []

    days: list[dict[str, Any]] = []
    for offset in range(7):
        day = week_start + dt.timedelta(days=offset)
        from_dt = dt.datetime.combine(day, dt.time(0, 0))
        to_dt = dt.datetime.combine(day, dt.time(23, 59))
        events = list_events_for_window(session, from_dt, to_dt)
        occupied = [(e.debut, e.fin or e.debut + dt.timedelta(hours=1)) for e in events]
        # charge = minutes occupées dans la fenêtre de travail
        win_start = dt.datetime.combine(day, dt.time(day_start_h, 0))
        win_end = dt.datetime.combine(day, dt.time(day_end_h, 0))
        load_min = 0
        for d0, f0 in occupied:
            lo, hi = max(d0, win_start), min(f0, win_end)
            if hi > lo:
                load_min += int((hi - lo).total_seconds() // 60)
        slots = free_slots(
            day, occupied, min_duration_min=block_min,
            day_start_h=day_start_h, day_end_h=day_end_h,
        )
        days.append({"date": day, "load_min": load_min, "slots": slots})

    blocks = select_deep_work_blocks(
        days, n_blocks=remaining, block_min=block_min, max_per_day=max_per_day
    )
    if dry_run or not blocks:
        return blocks

    created: list[dict[str, Any]] = []
    for b in blocks:
        if b["debut"] in existing_debuts:
            continue
        session.add(Evenement(
            titre=b["titre"], debut=b["debut"], fin=b["fin"],
            categorie=b["categorie"], couleur=b["couleur"], source=FOCUS_SOURCE,
        ))
        created.append(b)
        existing_debuts.add(b["debut"])
    session.commit()
    return created
