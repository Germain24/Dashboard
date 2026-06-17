"""Sous-routeur Budget : catégories, règles, enveloppes (#507)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.budget.schemas import CategoryCreate, EnvelopeCreate, RuleCreate
from app.core.db import get_session
from app.models.budget import BudgetRule
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
    return cat_svc.create_category(session, **body.model_dump())


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
