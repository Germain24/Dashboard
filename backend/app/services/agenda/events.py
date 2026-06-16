"""CRUD des événements ponctuels et expansion des récurrences.

Les récurrences sont stockées dans RegleRecurrence et expandées
virtuellement à la requête (non persistées par occurrence).
"""

from __future__ import annotations

import datetime as dt
from app.core.timeutil import utcnow
from typing import Any, Optional

from sqlalchemy import exc as sa_exc
from sqlmodel import Session, select

from app.models.agenda import Evenement, RegleRecurrence
from app.services.agenda.recurrence import expand_rules_for_window


# ── CRUD Evenement ──────────────────────────────────────────────────────────

def list_events_in_window(
    session: Session,
    from_dt: dt.datetime,
    to_dt: dt.datetime,
) -> list[Evenement]:
    stmt = (
        select(Evenement)
        .where(Evenement.debut < to_dt)
        .where(Evenement.fin > from_dt if Evenement.fin is not None else Evenement.debut >= from_dt)
        .order_by(Evenement.debut)
    )
    return list(session.exec(stmt).all())


def list_events_for_window(
    session: Session,
    from_dt: dt.datetime,
    to_dt: dt.datetime,
) -> list[Evenement]:
    """Événements dont le début tombe dans la fenêtre."""
    stmt = (
        select(Evenement)
        .where(Evenement.debut >= from_dt)
        .where(Evenement.debut < to_dt)
        .order_by(Evenement.debut)
    )
    return list(session.exec(stmt).all())


def create_event(session: Session, data: dict[str, Any]) -> Evenement:
    ev = Evenement(**data)
    session.add(ev)
    session.commit()
    session.refresh(ev)
    return ev


def get_event(session: Session, event_id: int) -> Optional[Evenement]:
    return session.get(Evenement, event_id)


def update_event(
    session: Session, event_id: int, data: dict[str, Any]
) -> Optional[Evenement]:
    ev = session.get(Evenement, event_id)
    if ev is None:
        return None
    for k, v in data.items():
        setattr(ev, k, v)
    session.add(ev)
    session.commit()
    session.refresh(ev)
    return ev


def delete_event(session: Session, event_id: int) -> bool:
    ev = session.get(Evenement, event_id)
    if ev is None:
        return False
    session.delete(ev)
    session.commit()
    return True


# ── CRUD RegleRecurrence ────────────────────────────────────────────────────

def list_recurrence_rules(session: Session) -> list[RegleRecurrence]:
    return list(session.exec(select(RegleRecurrence).order_by(RegleRecurrence.id)).all())


def create_recurrence_rule(session: Session, data: dict[str, Any]) -> RegleRecurrence:
    rule = RegleRecurrence(**data)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def get_recurrence_rule(session: Session, rule_id: int) -> Optional[RegleRecurrence]:
    return session.get(RegleRecurrence, rule_id)


def update_recurrence_rule(
    session: Session, rule_id: int, data: dict[str, Any]
) -> Optional[RegleRecurrence]:
    rule = session.get(RegleRecurrence, rule_id)
    if rule is None:
        return None
    for k, v in data.items():
        setattr(rule, k, v)
    rule.updated_at = utcnow()
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def delete_recurrence_rule(session: Session, rule_id: int) -> bool:
    rule = session.get(RegleRecurrence, rule_id)
    if rule is None:
        return False
    session.delete(rule)
    session.commit()
    return True


# ── Vue combinée : événements ponctuels + occurrences virtuelles ────────────

def get_full_calendar(
    session: Session,
    from_dt: dt.datetime,
    to_dt: dt.datetime,
) -> list[dict[str, Any]]:
    """Retourne événements persistés + occurrences de récurrences."""
    events = list_events_for_window(session, from_dt, to_dt)
    rules = list_recurrence_rules(session)
    virtual = expand_rules_for_window(rules, from_dt.date(), to_dt.date())

    result: list[dict[str, Any]] = []
    for ev in events:
        result.append({
            "id": ev.id, "titre": ev.titre, "debut": ev.debut, "fin": ev.fin,
            "lieu": ev.lieu, "description": ev.description, "source": ev.source,
            "source_id": ev.source_id, "categorie": ev.categorie,
            "couleur": ev.couleur, "recurrence_id": ev.recurrence_id,
            "is_virtual": False,
        })
    result.extend(virtual)
    result.sort(key=lambda x: x["debut"])
    return result
