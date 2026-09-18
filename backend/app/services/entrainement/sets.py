"""CRUD des séries (SetSerie) — sous-module dédié."""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from app.models.entrainement import SetSerie


def list_sets_for_seance(session: Session, seance_id: int) -> list[SetSerie]:
    return list(
        session.exec(
            select(SetSerie)
            .where(SetSerie.seance_id == seance_id)
            .order_by(SetSerie.ordre, SetSerie.id)
        ).all()
    )


def list_sets_for_exercice(
    session: Session,
    exercice_id: int,
) -> list[SetSerie]:
    return list(
        session.exec(
            select(SetSerie)
            .where(SetSerie.exercice_id == exercice_id)
            .order_by(SetSerie.id)
        ).all()
    )


def add_set(
    session: Session,
    *,
    seance_id: int,
    exercice_id: int,
    reps: int,
    poids_kg: float,
    rpe: Optional[float] = None,
    echec: bool = False,
    ordre: Optional[int] = None,
) -> SetSerie:
    """Ajoute une série à une séance. Si `ordre` est None, on prend le max+1."""
    if ordre is None:
        rows = list_sets_for_seance(session, seance_id)
        ordre = (max((s.ordre for s in rows), default=-1) + 1) if rows else 0
    s = SetSerie(
        seance_id=seance_id,
        exercice_id=exercice_id,
        ordre=ordre,
        reps=reps,
        poids_kg=poids_kg,
        rpe=rpe,
        echec=echec,
    )
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def update_set(session: Session, set_id: int, **changes) -> Optional[SetSerie]:
    s = session.get(SetSerie, set_id)
    if s is None:
        return None
    for k, v in changes.items():
        if v is None:
            continue
        if not hasattr(s, k):
            continue
        setattr(s, k, v)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def delete_set(session: Session, set_id: int) -> bool:
    s = session.get(SetSerie, set_id)
    if s is None:
        return False
    session.delete(s)
    session.commit()
    return True


def set_to_dict(s: SetSerie) -> dict:
    """Sérialisation utilitaire (pour le 1RM, les totaux, etc.)."""
    return {
        "id": s.id,
        "seance_id": s.seance_id,
        "exercice_id": s.exercice_id,
        "ordre": s.ordre,
        "reps": s.reps,
        "poids_kg": s.poids_kg,
        "rpe": s.rpe,
        "echec": s.echec,
    }
