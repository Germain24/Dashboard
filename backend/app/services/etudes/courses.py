"""CRUD des cours."""

from __future__ import annotations

import datetime as dt
from app.core.timeutil import utcnow
from typing import Any, Optional

from sqlmodel import Session, select

from app.models.etudes import Cours


def list_cours(
    session: Session,
    semestre: Optional[str] = None,
    actif: Optional[bool] = None,
) -> list[Cours]:
    stmt = select(Cours)
    if semestre is not None:
        stmt = stmt.where(Cours.semestre == semestre)
    if actif is not None:
        stmt = stmt.where(Cours.actif == actif)
    return list(session.exec(stmt.order_by(Cours.code)).all())


def get_cours(session: Session, cours_id: int) -> Optional[Cours]:
    return session.get(Cours, cours_id)


def create_cours(session: Session, data: dict[str, Any]) -> Cours:
    cours = Cours(**data)
    session.add(cours)
    session.commit()
    session.refresh(cours)
    return cours


def update_cours(
    session: Session, cours_id: int, data: dict[str, Any]
) -> Optional[Cours]:
    cours = session.get(Cours, cours_id)
    if cours is None:
        return None
    for k, v in data.items():
        setattr(cours, k, v)
    cours.updated_at = utcnow()
    session.add(cours)
    session.commit()
    session.refresh(cours)
    return cours


def delete_cours(session: Session, cours_id: int) -> bool:
    """Supprime un cours + ses évaluations et sessions liées (cascade manuelle)."""
    from app.models.etudes import Evaluation, SessionEtude

    cours = session.get(Cours, cours_id)
    if cours is None:
        return False
    # Cascade manuelle (SQLite ne le fait pas automatiquement — PLAN note 16)
    for ev in session.exec(
        select(Evaluation).where(Evaluation.cours_id == cours_id)
    ).all():
        session.delete(ev)
    for se in session.exec(
        select(SessionEtude).where(SessionEtude.cours_id == cours_id)
    ).all():
        session.delete(se)
    session.delete(cours)
    session.commit()
    return True


def semestres_distincts(session: Session) -> list[str]:
    """Retourne la liste des semestres présents, triés."""
    rows = session.exec(select(Cours.semestre)).all()
    return sorted(set(rows))
