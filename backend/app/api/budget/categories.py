"""Sous-routeur Budget : catégories, règles, enveloppes (#507)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.budget.schemas import CategoryCreate, CategoryUpdate, EnvelopeCreate, RuleCreate
from app.core.db import get_session
from app.models.budget import BudgetCategory, BudgetRule
from app.repositories.budget import BudgetRuleRepository
from app.services.budget import categories as cat_svc
from app.services.budget import envelopes as env_svc
from app.services.budget import rules as rules_svc

router = APIRouter()


@router.get("/categories")
def list_categories(session: Session = Depends(get_session)):
    return cat_svc.get_categories(session)


@router.post("/categories", status_code=201)
def create_category(body: CategoryCreate, session: Session = Depends(get_session)):
    nom = body.nom.strip()
    if not nom:
        raise HTTPException(422, "Le nom de catégorie est obligatoire")
    if body.parent_id is not None and session.get(BudgetCategory, body.parent_id) is None:
        raise HTTPException(422, "Catégorie parente introuvable")
    duplicate = session.exec(
        select(BudgetCategory).where(
            BudgetCategory.nom == nom,
            BudgetCategory.parent_id == body.parent_id,
        )
    ).first()
    if duplicate:
        raise HTTPException(409, "Cette catégorie existe déjà à ce niveau")
    return cat_svc.create_category(session, nom=nom, parent_id=body.parent_id, couleur=body.couleur)


@router.patch("/categories/{id}")
def update_category(id: int, body: CategoryUpdate, session: Session = Depends(get_session)):
    category = session.get(BudgetCategory, id)
    if category is None:
        raise HTTPException(404, "Catégorie introuvable")

    fields = body.model_fields_set
    nom = body.nom.strip() if "nom" in fields and body.nom is not None else category.nom
    parent_id = body.parent_id if "parent_id" in fields else category.parent_id
    couleur = body.couleur if "couleur" in fields and body.couleur is not None else category.couleur
    if not nom:
        raise HTTPException(422, "Le nom de catégorie est obligatoire")

    if parent_id is not None:
        parent = session.get(BudgetCategory, parent_id)
        if parent is None:
            raise HTTPException(422, "Catégorie parente introuvable")
        current = parent
        visited: set[int] = set()
        while current is not None and current.id not in visited:
            if current.id == category.id:
                raise HTTPException(
                    422,
                    "Une catégorie ne peut pas être déplacée sous elle-même ou l'une de ses sous-catégories",
                )
            visited.add(current.id)
            current = session.get(BudgetCategory, current.parent_id) if current.parent_id is not None else None

    duplicate = session.exec(
        select(BudgetCategory).where(
            BudgetCategory.nom == nom,
            BudgetCategory.parent_id == parent_id,
            BudgetCategory.id != id,
        )
    ).first()
    if duplicate:
        raise HTTPException(409, "Cette catégorie existe déjà à ce niveau")

    category.nom = nom
    category.parent_id = parent_id
    category.couleur = couleur
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.get("/rules")
def list_rules(session: Session = Depends(get_session)):
    return session.exec(select(BudgetRule)).all()


@router.post("/rules", status_code=201)
def create_rule(body: RuleCreate, session: Session = Depends(get_session)):
    return BudgetRuleRepository(session).create(body.model_dump())


@router.delete("/rules/{id}", status_code=204)
def delete_rule(id: int, session: Session = Depends(get_session)):
    if not BudgetRuleRepository(session).delete_by_id(id):
        raise HTTPException(404)


@router.post("/rules/apply")
def apply_rules(session: Session = Depends(get_session)):
    return {"updated": rules_svc.reapply_all_rules(session)}


@router.get("/rules/suggestions")
def suggest_rules(min_occurrences: int = 3, session: Session = Depends(get_session)):
    """Règles apprises de l'historique catégorisé à la main, sans rien créer (#258)."""
    return rules_svc.learn_rules(session, min_occurrences=min_occurrences, apply=False)


@router.post("/rules/learn")
def learn_rules(min_occurrences: int = 3, session: Session = Depends(get_session)):
    """Crée les règles apprises puis recatégorise les transactions (#258)."""
    return rules_svc.learn_rules(session, min_occurrences=min_occurrences, apply=True)


@router.get("/envelopes")
def list_envelopes(month: str, session: Session = Depends(get_session)):
    return env_svc.get_envelope_status(session, month)


@router.post("/envelopes", status_code=201)
def create_envelope(body: EnvelopeCreate, session: Session = Depends(get_session)):
    return env_svc.upsert_envelope(session, body.category_id, body.mois, body.montant)
