"""CRUD du catalogue d'exercices."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.entrainement import Exercice
from app.services.entrainement.exercises_seed import seed_exercices


def ensure_catalogue(session: Session) -> int:
    """Garantit qu'il y a au moins le catalogue de base. Idempotent.

    Retourne le nombre d'exercices créés à cet appel.
    """
    return seed_exercices(session)


def list_exercices(
    session: Session,
    categorie: Optional[str] = None,
) -> list[Exercice]:
    stmt = select(Exercice)
    if categorie:
        stmt = stmt.where(Exercice.categorie == categorie)
    stmt = stmt.order_by(Exercice.categorie, Exercice.nom)
    return list(session.exec(stmt).all())


def get_exercice(session: Session, exercice_id: int) -> Optional[Exercice]:
    return session.get(Exercice, exercice_id)


def get_exercice_by_nom(session: Session, nom: str) -> Optional[Exercice]:
    return session.exec(select(Exercice).where(Exercice.nom == nom)).first()


def create_exercice(
    session: Session,
    *,
    nom: str,
    categorie: str,
    muscles: Optional[list[str]] = None,
    type_mouvement: str = "compose",
    unilateral: bool = False,
    source: str = "manual",
    note: Optional[str] = None,
) -> Exercice:
    """Crée un exercice. Si le nom existe déjà, retourne l'existant (upsert
    soft : pas de modification silencieuse).

    Robuste aux race conditions : si un autre thread insère le même nom entre
    notre check `get_exercice_by_nom` et notre `commit`, on attrape
    `IntegrityError`, on rollback, et on retourne l'enregistrement existant.
    """
    existing = get_exercice_by_nom(session, nom)
    if existing:
        return existing
    e = Exercice(
        nom=nom,
        categorie=categorie,
        muscles=list(muscles or []),
        type_mouvement=type_mouvement,
        unilateral=unilateral,
        source=source,
        note=note,
    )
    session.add(e)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        # Un autre thread l'a inséré pendant qu'on essayait → on relit
        existing = get_exercice_by_nom(session, nom)
        if existing is not None:
            return existing
        raise
    session.refresh(e)
    return e


def update_exercice(
    session: Session,
    exercice_id: int,
    **changes,
) -> Optional[Exercice]:
    e = get_exercice(session, exercice_id)
    if e is None:
        return None
    for k, v in changes.items():
        if v is None:
            continue
        if not hasattr(e, k):
            continue
        setattr(e, k, v)
    session.add(e)
    session.commit()
    session.refresh(e)
    return e


def delete_exercice(session: Session, exercice_id: int) -> bool:
    e = get_exercice(session, exercice_id)
    if e is None:
        return False
    session.delete(e)
    session.commit()
    return True
