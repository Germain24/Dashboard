"""CRUD des tâches (Tache).

Tri par urgence : (priorité ASC, deadline ASC nulls-last).
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from sqlmodel import Session, select

from app.models.agenda import Tache


def list_tasks(
    session: Session,
    statut: Optional[str] = None,
    categorie: Optional[str] = None,
) -> list[Tache]:
    stmt = select(Tache)
    if statut is not None:
        stmt = stmt.where(Tache.statut == statut)
    if categorie is not None:
        stmt = stmt.where(Tache.categorie == categorie)
    # Tri : priorité ASC, deadline nulls-last, id ASC
    tasks = list(session.exec(stmt).all())
    tasks.sort(key=lambda t: (
        t.priorite,
        t.deadline or dt.date(9999, 12, 31),
        t.id or 0,
    ))
    return tasks


def create_task(session: Session, data: dict[str, Any]) -> Tache:
    tache = Tache(**data)
    session.add(tache)
    session.commit()
    session.refresh(tache)
    return tache


def get_task(session: Session, task_id: int) -> Optional[Tache]:
    return session.get(Tache, task_id)


def update_task(
    session: Session, task_id: int, data: dict[str, Any]
) -> Optional[Tache]:
    tache = session.get(Tache, task_id)
    if tache is None:
        return None
    for k, v in data.items():
        setattr(tache, k, v)
    tache.updated_at = dt.datetime.utcnow()
    session.add(tache)
    session.commit()
    session.refresh(tache)
    return tache


def mark_done(session: Session, task_id: int) -> Optional[Tache]:
    return update_task(session, task_id, {"statut": "done"})


def delete_task(session: Session, task_id: int) -> bool:
    tache = session.get(Tache, task_id)
    if tache is None:
        return False
    session.delete(tache)
    session.commit()
    return True


def tasks_due_today(session: Session) -> list[Tache]:
    today = dt.date.today()
    stmt = (
        select(Tache)
        .where(Tache.statut == "todo")
        .where(Tache.deadline <= today)
    )
    tasks = list(session.exec(stmt).all())
    tasks.sort(key=lambda t: (t.priorite, t.id or 0))
    return tasks
