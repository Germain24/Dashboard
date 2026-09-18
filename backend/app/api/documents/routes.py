"""Routes Documents (#548)."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.core.db import get_session
from app.services.documents import (
    classify_expiry,
    create_document,
    delete_document,
    get_documents,
    update_document,
    upcoming_expirations,
)

router = APIRouter()


class DocumentCreate(BaseModel):
    titre: str
    type: str = "autre"
    notes: str = ""
    date_expiration: dt.date | None = None
    date_emission: dt.date | None = None
    organisme: str = ""
    fichier_url: str | None = None
    tags: list[str] = []


class DocumentPatch(BaseModel):
    titre: str | None = None
    type: str | None = None
    notes: str | None = None
    date_expiration: dt.date | None = None
    date_emission: dt.date | None = None
    organisme: str | None = None
    fichier_url: str | None = None
    tags: list[str] | None = None


def _enrich(doc) -> dict:
    return {
        **doc.model_dump(),
        "statut_expiration": classify_expiry(doc.date_expiration),
    }


@router.get("/documents")
def list_documents(
    type: str | None = None,
    q: str | None = None,
    session: Session = Depends(get_session),
):
    docs = get_documents(session, type=type, q=q)
    return [_enrich(d) for d in docs]


@router.post("/documents", status_code=201)
def add_document(body: DocumentCreate, session: Session = Depends(get_session)):
    doc = create_document(session, **body.model_dump())
    return _enrich(doc)


@router.patch("/documents/{doc_id}")
def patch_document(doc_id: int, body: DocumentPatch, session: Session = Depends(get_session)):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    doc = update_document(session, doc_id, patch)
    if not doc:
        raise HTTPException(404)
    return _enrich(doc)


@router.delete("/documents/{doc_id}", status_code=204)
def remove_document(doc_id: int, session: Session = Depends(get_session)):
    if not delete_document(session, doc_id):
        raise HTTPException(404)


@router.get("/documents/echeances")
def get_echeances(days: int = 30, session: Session = Depends(get_session)):
    docs = upcoming_expirations(session, days=days)
    return [_enrich(d) for d in docs]
