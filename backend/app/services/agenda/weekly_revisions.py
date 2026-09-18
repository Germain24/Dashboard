"""Planification hebdomadaire des révisions par cours.

Les cours sont révisés une fois par semaine pendant 2 h. Le dimanche, le créneau
Shopify (12 h–17 h) est préféré : une séance de 1 h 30 y suffit. Si le travail ou
un autre événement empêche cette séance, le planificateur cherche 2 h à la maison.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.models.agenda import Evenement
from app.services.agenda.events import get_full_calendar
from app.services.agenda.slots import free_slots

SHOPIFY_WEEKDAY = 6  # dimanche, Python : lundi=0
SHOPIFY_START_H = 12
SHOPIFY_END_H = 17
SHOPIFY_SESSION_MIN = 90
HOME_SESSION_MIN = 120
BUFFER_MIN = 15
REVISION_COLOR = "#2563EB"


@dataclass(frozen=True)
class RevisionBlock:
    course: str
    debut: dt.datetime
    fin: dt.datetime
    lieu: str


@dataclass
class RevisionProposal:
    week_start: dt.date
    blocks: list[RevisionBlock] = field(default_factory=list)
    non_places: list[str] = field(default_factory=list)


def _with_buffer(
    intervals: list[tuple[dt.datetime, dt.datetime]],
) -> list[tuple[dt.datetime, dt.datetime]]:
    padding = dt.timedelta(minutes=BUFFER_MIN)
    return [(start - padding, end + padding) for start, end in intervals]


def _find_slot(
    day: dt.date,
    occupied: list[tuple[dt.datetime, dt.datetime]],
    duration_min: int,
    *,
    day_start_h: int,
    day_end_h: int,
    preferred_times: list[tuple[int, int]] | None = None,
) -> tuple[dt.datetime, dt.datetime] | None:
    slots = free_slots(
        day,
        _with_buffer(occupied),
        min_duration_min=duration_min,
        day_start_h=day_start_h,
        day_end_h=day_end_h,
    )
    duration = dt.timedelta(minutes=duration_min)
    for hour, minute in preferred_times or []:
        preferred = dt.datetime.combine(day, dt.time(hour, minute))
        if any(
            slot["debut"] <= preferred and preferred + duration <= slot["fin"] for slot in slots
        ):
            return preferred, preferred + duration
    if slots:
        start = slots[0]["debut"]
        return start, start + duration
    return None


def _home_times(moment: str | None) -> list[tuple[int, int]]:
    return {
        "matin": [(7, 30), (9, 0), (10, 30)],
        "aprem": [(12, 30), (14, 0), (16, 0)],
        "soir": [(18, 0), (19, 30), (20, 30)],
    }.get(moment or "", [(9, 0), (14, 0)])


def plan_weekly_revisions(
    week_start: dt.date,
    courses: list[str],
    fixed_by_day: dict[dt.date, list[tuple[dt.datetime, dt.datetime]]],
    *,
    home_moment: str | None = None,
) -> RevisionProposal:
    """Planifie une révision unique par cours sur une semaine dimanche–samedi."""
    if week_start.weekday() != SHOPIFY_WEEKDAY:
        raise ValueError("La semaine de révision doit commencer un dimanche.")

    days = [week_start + dt.timedelta(days=offset) for offset in range(7)]
    occupied = {day: list(fixed_by_day.get(day, [])) for day in days}
    proposal = RevisionProposal(week_start=week_start)
    unique_courses = list(dict.fromkeys(name.strip() for name in courses if name.strip()))
    home_preferred_times = _home_times(home_moment)

    def add(course: str, slot: tuple[dt.datetime, dt.datetime], lieu: str) -> None:
        proposal.blocks.append(RevisionBlock(course, slot[0], slot[1], lieu))
        occupied[slot[0].date()].append(slot)

    for course in unique_courses:
        shopify = _find_slot(
            week_start,
            occupied[week_start],
            SHOPIFY_SESSION_MIN,
            day_start_h=SHOPIFY_START_H,
            day_end_h=SHOPIFY_END_H,
        )
        if shopify:
            add(course, shopify, "Shopify")
            continue

        # Une séance à la maison passe après la fenêtre Shopify et cherche
        # d'abord un autre jour de la semaine.
        placed = False
        for day in days[1:] + days[:1]:
            home = _find_slot(
                day,
                occupied[day],
                HOME_SESSION_MIN,
                day_start_h=7,
                day_end_h=23,
                preferred_times=home_preferred_times,
            )
            if home:
                add(course, home, "Maison")
                placed = True
                break
        if not placed:
            proposal.non_places.append(f"Révision « {course} » : aucun créneau cette semaine")

    proposal.blocks.sort(key=lambda block: block.debut)
    return proposal


def run_weekly_revisions(session: Session, run_date: dt.date | None = None) -> str:
    """Prépare la prochaine semaine dimanche–samedi (job du dimanche matin)."""
    today = run_date or dt.date.today()
    days_until_sunday = (SHOPIFY_WEEKDAY - today.weekday()) % 7
    return _run_for_week(session, today + dt.timedelta(days=days_until_sunday))


def replan_current_weekly_revisions(
    session: Session, run_date: dt.date | None = None
) -> str:
    """Recalcule la semaine en cours après un changement de shift ou de cours."""
    today = run_date or dt.date.today()
    days_since_sunday = (today.weekday() + 1) % 7
    return _run_for_week(session, today - dt.timedelta(days=days_since_sunday))


def _run_for_week(session: Session, week_start: dt.date) -> str:
    """Reconstruit les blocs de révision pour la semaine donnée."""
    from app.services.agenda.preferences import get_preferences

    week_end = week_start + dt.timedelta(days=6)
    from_dt = dt.datetime.combine(week_start, dt.time.min)
    to_dt = dt.datetime.combine(week_end + dt.timedelta(days=1), dt.time.min)

    # Supprime le plan précédent de cette semaine et les anciennes révisions
    # du planificateur général, puis le reconstruit sans doublons.
    persisted = session.exec(
        select(Evenement).where(Evenement.debut >= from_dt).where(Evenement.debut < to_dt)
    ).all()
    protected_revision_events = []
    for event in persisted:
        if event.source == "revision_planner" and event.debut.date() < dt.date.today():
            protected_revision_events.append(event)
    for event in persisted:
        if event.source == "revision_planner" or (
            event.source == "planner" and event.titre.startswith("Révision —")
        ):
            if event in protected_revision_events:
                continue
            session.delete(event)
    session.flush()

    calendar = get_full_calendar(session, from_dt, to_dt)
    courses: list[str] = []
    seen: set[str] = set()
    already_revised = {
        event.titre.removeprefix("Révision — ").strip()
        for event in protected_revision_events
    }
    fixed_by_day: dict[dt.date, list[tuple[dt.datetime, dt.datetime]]] = {}
    for item in calendar:
        # Les repas automatiques sont flexibles : ils pourront être déplacés
        # dans une pause de travail ou superposés à une révision.
        if item.get("source") == "planner" and item.get("titre") in {
            "Petit-déjeuner", "Déjeuner", "Dîner"
        }:
            continue
        if item.get("source") != "revision_planner" and item.get("categorie") == "cours":
            title = (item.get("titre") or "Cours").strip()
            if title not in seen and title not in already_revised:
                courses.append(title)
                seen.add(title)
        start, end = item.get("debut"), item.get("fin")
        if not start or not end:
            continue
        if item.get("source") == "revision_planner" and start.date() >= dt.date.today():
            continue
        if item.get("source") == "planner" and (item.get("titre") or "").startswith("Révision —"):
            continue
        fixed_by_day.setdefault(start.date(), []).append((start, end))
        if end.date() > start.date():
            fixed_by_day.setdefault(end.date(), []).append((start, end))

    # Le module Travail est aussi une source d'obstacles; les shifts iCal de
    # 7shifts sont déjà inclus parmi les événements fixes ci-dessus.
    try:
        from app.services.travail.shifts import list_shifts_for_window

        for shift in list_shifts_for_window(session, from_dt, to_dt):
            start, end = shift.get("debut"), shift.get("fin")
            if start and end:
                fixed_by_day.setdefault(start.date(), []).append((start, end))
    except Exception:
        pass

    moments = get_preferences().get("moments", {})
    proposal = plan_weekly_revisions(
        week_start,
        courses,
        fixed_by_day,
        home_moment=moments.get("etudes"),
    )
    for block in proposal.blocks:
        session.add(
            Evenement(
                titre=f"Révision — {block.course}",
                debut=block.debut,
                fin=block.fin,
                lieu=block.lieu,
                description="Révision hebdomadaire planifiée.",
                source="revision_planner",
                categorie="cours",
                couleur=REVISION_COLOR,
            )
        )
    session.commit()

    shopify_count = sum(block.lieu == "Shopify" for block in proposal.blocks)
    home_count = len(proposal.blocks) - shopify_count
    summary = (
        f"Révisions du {week_start:%d/%m} au {week_end:%d/%m} : "
        f"{len(proposal.blocks)} planifiée(s), {shopify_count} à Shopify, "
        f"{home_count} à la maison, {len(proposal.non_places)} sans créneau."
    )
    if proposal.non_places:
        summary += " À placer manuellement : " + "; ".join(proposal.non_places)
    return summary


def replan_future_revisions_for_window(
    session: Session,
    window_start: dt.date,
    window_end: dt.date,
) -> None:
    """Repositionne les révisions futures autour des nouveaux blocs prioritaires."""
    week_start = window_start - dt.timedelta(days=(window_start.weekday() + 1) % 7)
    while week_start <= window_end:
        if week_start + dt.timedelta(days=6) >= dt.date.today():
            _run_for_week(session, week_start)
        week_start += dt.timedelta(days=7)
