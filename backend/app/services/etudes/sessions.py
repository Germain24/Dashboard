"""CRUD des sessions d'étude (Pomodoro / libre).

Décision 3.A : inclus dès V1.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from sqlmodel import Session, select

from app.models.etudes import SessionEtude


def list_sessions(
    session: Session,
    cours_id: Optional[int] = None,
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
) -> list[SessionEtude]:
    stmt = select(SessionEtude)
    if cours_id is not None:
        stmt = stmt.where(SessionEtude.cours_id == cours_id)
    if date_from is not None:
        stmt = stmt.where(SessionEtude.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(SessionEtude.date <= date_to)
    return list(session.exec(stmt.order_by(SessionEtude.date.desc())).all())  # type: ignore[union-attr]


def get_session(session: Session, session_id: int) -> Optional[SessionEtude]:
    return session.get(SessionEtude, session_id)


def create_session(session: Session, data: dict[str, Any]) -> SessionEtude:
    se = SessionEtude(**data)
    session.add(se)
    session.commit()
    session.refresh(se)
    return se


def update_session(
    session: Session, session_id: int, data: dict[str, Any]
) -> Optional[SessionEtude]:
    se = session.get(SessionEtude, session_id)
    if se is None:
        return None
    for k, v in data.items():
        setattr(se, k, v)
    session.add(se)
    session.commit()
    session.refresh(se)
    return se


def delete_session(session: Session, session_id: int) -> bool:
    se = session.get(SessionEtude, session_id)
    if se is None:
        return False
    session.delete(se)
    session.commit()
    return True


def total_minutes_par_cours(
    session: Session,
    cours_id: int,
    date_from: Optional[dt.date] = None,
) -> int:
    """Cumul des minutes de travail pour un cours donné."""
    sessions = list_sessions(session, cours_id=cours_id, date_from=date_from)
    return sum(s.duree_min for s in sessions)
