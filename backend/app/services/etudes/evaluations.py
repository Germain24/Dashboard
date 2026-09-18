"""CRUD des évaluations + bridge Agenda (silencieux)."""

from __future__ import annotations

import datetime as dt
from app.core.timeutil import utcnow
import logging
from typing import Any, Optional

from sqlmodel import Session, select

from app.models.etudes import Evaluation

log = logging.getLogger(__name__)


def list_evaluations(
    session: Session,
    cours_id: Optional[int] = None,
    upcoming_only: bool = False,
) -> list[Evaluation]:
    stmt = select(Evaluation)
    if cours_id is not None:
        stmt = stmt.where(Evaluation.cours_id == cours_id)
    if upcoming_only:
        today = dt.date.today()
        stmt = stmt.where(Evaluation.date_limite >= today)
    return list(
        session.exec(
            stmt.order_by(Evaluation.date_limite.asc())  # type: ignore[union-attr]
        ).all()
    )


def get_evaluation(session: Session, eval_id: int) -> Optional[Evaluation]:
    return session.get(Evaluation, eval_id)


def create_evaluation(
    session: Session, data: dict[str, Any]
) -> Evaluation:
    ev = Evaluation(**data)
    session.add(ev)
    session.commit()
    session.refresh(ev)

    # Bridge Agenda silencieux (note 20 du PLAN)
    if ev.date_limite is not None:
        _try_create_agenda_task(session, ev)

    return ev


def update_evaluation(
    session: Session, eval_id: int, data: dict[str, Any]
) -> Optional[Evaluation]:
    ev = session.get(Evaluation, eval_id)
    if ev is None:
        return None
    for k, v in data.items():
        setattr(ev, k, v)
    ev.updated_at = utcnow()
    session.add(ev)
    session.commit()
    session.refresh(ev)
    return ev


def delete_evaluation(session: Session, eval_id: int) -> bool:
    ev = session.get(Evaluation, eval_id)
    if ev is None:
        return False
    session.delete(ev)
    session.commit()
    return True


def _try_create_agenda_task(session: Session, ev: Evaluation) -> None:
    """Crée une Tache Agenda liée à l'évaluation.

    Bridge silencieux : toute exception est absorbée (PLAN note 20).
    """
    try:
        from app.models.etudes import Cours
        from app.services.agenda import tasks as agenda_tasks
        from app.services.etudes.constants import PRIORITE_PAR_TYPE

        cours = session.get(Cours, ev.cours_id)
        cours_code = cours.code if cours else f"cours#{ev.cours_id}"

        priorite = PRIORITE_PAR_TYPE.get(ev.type_eval, 4)

        agenda_tasks.create_task(
            session,
            {
                "titre": f"{cours_code} — {ev.titre}",
                "deadline": ev.date_limite,
                "priorite": priorite,
                "source": "etudes",
                "source_id": str(ev.id),
                "categorie": "devoir",
            },
        )
        log.debug("Bridge Agenda OK pour évaluation #%s", ev.id)
    except Exception:  # noqa: BLE001
        log.warning(
            "Bridge Agenda échoué pour évaluation #%s (non bloquant)",
            ev.id,
            exc_info=True,
        )
