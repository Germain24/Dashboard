"""Sous-routeur Budget : transactions + import CSV (#507)."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session

from app.api.budget.schemas import TagsUpdate, TransactionCategoryUpdate, TransactionCreate
from app.core.db import get_session
from app.models.budget import BudgetCategory
from app.repositories.budget import BudgetTransactionRepository
from app.services.budget import imports as import_svc
from app.services.budget import transactions as tx_svc

router = APIRouter()


@router.get("/transactions")
def list_transactions(
    from_date: dt.date | None = None,
    to_date: dt.date | None = None,
    category_id: int | None = None,
    session: Session = Depends(get_session),
):
    return tx_svc.get_transactions(session, from_date, to_date, category_id)


@router.get("/investment-flows")
def investment_flows(
    from_date: dt.date | None = None,
    to_date: dt.date | None = None,
    session: Session = Depends(get_session),
):
    """Apports nets vers les plateformes, regroupés par plateforme et devise."""
    from app.services.budget.investment_flows import get_investment_flow_summary

    return get_investment_flow_summary(session, from_date=from_date, to_date=to_date)


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


@router.patch("/transactions/{id}/category")
def update_transaction_category(
    id: int,
    body: TransactionCategoryUpdate,
    session: Session = Depends(get_session),
):
    """Assigne ou retire une catégorie à une transaction."""
    repo = BudgetTransactionRepository(session)
    transaction = repo.get(id)
    if not transaction:
        raise HTTPException(404, "Transaction introuvable")
    if body.category_id is not None and session.get(BudgetCategory, body.category_id) is None:
        raise HTTPException(422, "Catégorie introuvable")
    return repo.update(transaction, {"category_id": body.category_id})


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
async def import_releve(
    file: UploadFile = File(...), compte: str = "principal", session: Session = Depends(get_session)
):
    """Importe un relevé : PDF (Desjardins, Banque Populaire, Westpac), CSV ou
    OFX/QFX (#256). Le format PDF est détecté par mot-clé dans le texte extrait
    — évite qu'un relevé non-Desjardins tombe silencieusement dans le parseur
    Desjardins (qui renverrait 0 transaction sans erreur)."""
    raw = await file.read()
    if raw[:4] == b"PK\x03\x04":  # Excel (.xlsx) -> relevé Wise
        from app.services.budget.wise import import_wise

        return import_wise(session, raw, "wise" if compte == "principal" else compte)
    from app.services.budget.desjardins_pdf import (
        _unwrap_pdf,
        extract_pdf_text,
        import_desjardins_pdf,
        looks_like_pdf,
    )

    if looks_like_pdf(raw):
        pdf = _unwrap_pdf(raw)
        sample = extract_pdf_text(pdf) if pdf else ""
        auto_compte = None if compte == "principal" else compte
        if "banque populaire" in sample.lower():
            from app.services.budget.banque_populaire_pdf import import_banque_populaire_pdf

            return import_banque_populaire_pdf(session, sample, auto_compte or "banquepopulaire")
        if "westpac" in sample.lower():
            from app.services.budget.westpac_pdf import import_westpac_pdf

            layout = extract_pdf_text(pdf, layout=True) if pdf else ""
            return import_westpac_pdf(session, layout, auto_compte or "westpac")
        # PDF (carte ou compte chèque) Desjardins, éventuellement emballé : compte
        # auto-détecté sauf si l'utilisateur a fixé un compte explicite.
        return import_desjardins_pdf(session, raw, auto_compte)
    return import_svc.import_transactions(session, raw.decode("utf-8", errors="replace"), compte)
