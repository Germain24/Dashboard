"""Sous-routeur Budget : transactions + import CSV (#507)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session

from app.api.budget.schemas import TagsUpdate, TransactionCreate
from app.core.db import get_session
from app.repositories.budget import BudgetTransactionRepository
from app.services.budget import imports as import_svc
from app.services.budget import transactions as tx_svc

router = APIRouter()


@router.get("/transactions")
def list_transactions(from_date: dt.date | None = None, to_date: dt.date | None = None,
                      category_id: int | None = None, session: Session = Depends(get_session)):
    return tx_svc.get_transactions(session, from_date, to_date, category_id)


@router.post("/transactions", status_code=201)
def create_transaction(body: TransactionCreate, session: Session = Depends(get_session)):
    return tx_svc.create_transaction(session, **body.model_dump())


@router.patch("/transactions/{id}")
def update_transaction(id: int, category_id: int, session: Session = Depends(get_session)):
    repo = BudgetTransactionRepository(session)
    t = repo.get(id)
    if not t:
        raise HTTPException(404)
    return repo.update(t, {"category_id": category_id})


@router.patch("/transactions/{id}/tags")
def update_transaction_tags(id: int, body: TagsUpdate, session: Session = Depends(get_session)):
    """Définit les tags d'une transaction (#119)."""
    repo = BudgetTransactionRepository(session)
    t = repo.get(id)
    if not t:
        raise HTTPException(404)
    return repo.update(t, {"tags": [s.strip() for s in body.tags if s.strip()]})


@router.delete("/transactions/{id}", status_code=204)
def delete_transaction(id: int, session: Session = Depends(get_session)):
    if not BudgetTransactionRepository(session).delete_by_id(id):
        raise HTTPException(404)


@router.post("/import")
async def import_releve(file: UploadFile = File(...), compte: str = "principal",
                        session: Session = Depends(get_session)):
    """Importe un relevé : PDF Mastercard Desjardins, CSV ou OFX/QFX (#256)."""
    raw = await file.read()
    if raw[:4] == b"PK\x03\x04":   # Excel (.xlsx) -> relevé Wise
        from app.services.budget.wise import import_wise
        return import_wise(session, raw, "wise" if compte == "principal" else compte)
    from app.services.budget.desjardins_pdf import import_desjardins_pdf, looks_like_pdf
    if looks_like_pdf(raw):
        # PDF (carte ou compte chèque), éventuellement emballé : compte auto-détecté
        # sauf si l'utilisateur a fixé un compte explicite (≠ défaut "principal").
        return import_desjardins_pdf(session, raw, None if compte == "principal" else compte)
    return import_svc.import_transactions(session, raw.decode("utf-8", errors="replace"), compte)
