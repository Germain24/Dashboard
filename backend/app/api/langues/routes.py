from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.api.langues.schemas import (
    PROJET_STATUTS,
    PROJET_TYPES,
    VOCAB_TYPES,
    ProjetCreate,
    ProjetUpdate,
    VocabCreate,
    VocabUpdate,
)
from app.core.db import get_session
from app.models.langues import ProjetInternational, VocabEntry

router = APIRouter(prefix="", tags=["langues"])


@router.get("/ping")
def ping():
    return {"module": "langues", "ready": True}


# ── Vocabulaire / kanjis ──────────────────────────────────────────


@router.get("/vocab")
def list_vocab(type: str | None = None, session: Session = Depends(get_session)):
    q = select(VocabEntry)
    if type:
        if type not in VOCAB_TYPES:
            raise HTTPException(422, f"type doit être parmi {VOCAB_TYPES}")
        q = q.where(VocabEntry.type == type)
    return session.exec(q.order_by(VocabEntry.maitrise, VocabEntry.terme)).all()


@router.get("/vocab/stats")
def vocab_stats(session: Session = Depends(get_session)):
    rows = session.exec(
        select(VocabEntry.type, VocabEntry.maitrise, func.count()).group_by(
            VocabEntry.type, VocabEntry.maitrise
        )
    ).all()
    stats = {t: {"total": 0, "par_maitrise": {}} for t in VOCAB_TYPES}
    for t, maitrise, n in rows:
        stats[t]["total"] += n
        stats[t]["par_maitrise"][str(maitrise)] = n
    return stats


@router.post("/vocab", status_code=201)
def create_vocab(body: VocabCreate, session: Session = Depends(get_session)):
    if body.type not in VOCAB_TYPES:
        raise HTTPException(422, f"type doit être parmi {VOCAB_TYPES}")
    entry = VocabEntry(**body.model_dump())
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


@router.patch("/vocab/{entry_id}")
def update_vocab(entry_id: int, body: VocabUpdate, session: Session = Depends(get_session)):
    entry = session.get(VocabEntry, entry_id)
    if not entry:
        raise HTTPException(404, f"Entrée {entry_id} introuvable")
    data = body.model_dump(exclude_unset=True)
    if "type" in data and data["type"] not in VOCAB_TYPES:
        raise HTTPException(422, f"type doit être parmi {VOCAB_TYPES}")
    for k, v in data.items():
        setattr(entry, k, v)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


@router.delete("/vocab/{entry_id}", status_code=204)
def delete_vocab(entry_id: int, session: Session = Depends(get_session)):
    entry = session.get(VocabEntry, entry_id)
    if not entry:
        raise HTTPException(404, f"Entrée {entry_id} introuvable")
    session.delete(entry)
    session.commit()


# ── Projets internationaux ────────────────────────────────────────


def _validate_projet(data: dict) -> None:
    if "type" in data and data["type"] not in PROJET_TYPES:
        raise HTTPException(422, f"type doit être parmi {PROJET_TYPES}")
    if "statut" in data and data["statut"] not in PROJET_STATUTS:
        raise HTTPException(422, f"statut doit être parmi {PROJET_STATUTS}")


@router.get("/projets")
def list_projets(session: Session = Depends(get_session)):
    return session.exec(
        select(ProjetInternational).order_by(
            ProjetInternational.echeance.is_(None), ProjetInternational.echeance
        )
    ).all()


@router.post("/projets", status_code=201)
def create_projet(body: ProjetCreate, session: Session = Depends(get_session)):
    _validate_projet(body.model_dump())
    projet = ProjetInternational(**body.model_dump())
    session.add(projet)
    session.commit()
    session.refresh(projet)
    return projet


@router.patch("/projets/{projet_id}")
def update_projet(projet_id: int, body: ProjetUpdate, session: Session = Depends(get_session)):
    projet = session.get(ProjetInternational, projet_id)
    if not projet:
        raise HTTPException(404, f"Projet {projet_id} introuvable")
    data = body.model_dump(exclude_unset=True)
    _validate_projet(data)
    for k, v in data.items():
        setattr(projet, k, v)
    session.add(projet)
    session.commit()
    session.refresh(projet)
    return projet


@router.delete("/projets/{projet_id}", status_code=204)
def delete_projet(projet_id: int, session: Session = Depends(get_session)):
    projet = session.get(ProjetInternational, projet_id)
    if not projet:
        raise HTTPException(404, f"Projet {projet_id} introuvable")
    session.delete(projet)
    session.commit()
