"""Recherche globale cross-modules (#546)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.core.db import get_session
from app.models.budget import BudgetTransaction
from app.models.cuisine import Recipe
from app.models.livres import Book

router = APIRouter(tags=["search"])


@router.get("/search")
def global_search(q: str, limit: int = 5, session: Session = Depends(get_session)):
    """Recherche rapide dans transactions, recettes et livres."""
    if not q or len(q.strip()) < 2:
        return {"results": []}

    term = f"%{q.strip().lower()}%"
    results = []

    # Transactions budget
    txns = session.exec(
        select(BudgetTransaction)
        .where(
            (BudgetTransaction.marchand.ilike(term))
            | (BudgetTransaction.description.ilike(term))
        )
        .limit(limit)
    ).all()
    for t in txns:
        results.append({
            "type": "transaction",
            "label": t.marchand or t.description or "Transaction",
            "hint": f"{t.montant:+.2f} €",
            "href": "/budget",
        })

    # Recettes
    recipes = session.exec(
        select(Recipe).where(Recipe.titre.ilike(term)).limit(limit)
    ).all()
    for r in recipes:
        results.append({
            "type": "recette",
            "label": r.titre,
            "hint": "Recette",
            "href": "/cuisine",
        })

    # Livres
    books = session.exec(
        select(Book).where(
            Book.titre.ilike(term) | Book.auteur.ilike(term)
        ).limit(limit)
    ).all()
    for b in books:
        results.append({
            "type": "livre",
            "label": b.titre,
            "hint": b.auteur or "Livre",
            "href": "/livres",
        })

    return {"results": results[:limit * 2]}
