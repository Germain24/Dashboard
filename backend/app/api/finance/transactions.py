"""Sous-routeur Finance : transactions (liste paginée, création, import CSV)."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from sqlmodel import Session, select

from app.core.db import get_session
from app.core.pagination import Pagination, paginate
from app.core.query_params import Sorting, apply_filters, apply_sort
from app.api.schemas_finance import (
    TransactionCreate, TransactionOut, ImportResultOut,
)
from app.services.finance.transactions import (
    create_transaction, delete_transaction, import_csv,
)

router = APIRouter()


@router.get("/transactions", response_model=list[TransactionOut])
def transactions_list(
    response: Response,
    ticker: Optional[str] = None,
    broker: Optional[str] = None,
    page: Pagination = Depends(),
    sorting: Sorting = Depends(),
    session: Session = Depends(get_session),
):
    # Pagination + tri/filtres standardisés ; corps = tableau, total dans X-Total-Count.
    from app.models.finance import Transaction
    stmt = select(Transaction)
    stmt = apply_filters(stmt, Transaction, {
        "ticker": ticker.upper() if ticker else None,
        "broker": broker,
    })
    if sorting.sort:
        stmt = apply_sort(stmt, Transaction, sorting,
                          allowed={"date", "ticker", "broker", "type", "quantite", "prix_unitaire"})
    else:
        stmt = stmt.order_by(Transaction.date.desc())
    return paginate(session, stmt, response, page)


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def transactions_create(body: TransactionCreate,
                        session: Session = Depends(get_session)):
    data = {
        "ticker": body.ticker.upper(),
        "type": body.type_transaction,
        "date": dt.datetime.combine(body.date_transaction, dt.time.min),
        "quantite": body.quantite,
        "prix_unitaire": body.prix_unitaire,
        "frais": body.frais,
        "devise": body.devise,
        "broker": body.broker,
        "note": body.note,
    }
    return create_transaction(session, data)


@router.delete("/transactions/{tx_id}", status_code=204)
def transactions_delete(tx_id: int, session: Session = Depends(get_session)):
    deleted = delete_transaction(session, tx_id)
    if not deleted:
        raise HTTPException(404, f"Transaction {tx_id} introuvable")


@router.post("/transactions/import", response_model=ImportResultOut)
async def transactions_import(
    file: UploadFile = File(...),
    broker: str = "auto",
    session: Session = Depends(get_session),
):
    content = await file.read()
    result = import_csv(session, content.decode("utf-8", errors="replace"),
                        broker_hint=broker)
    return ImportResultOut(**result)
