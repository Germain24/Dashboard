"""Marge de crédit : profil, comptes, historique de pointage, règles de seuils, feuille de route."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.core.db import get_session
from app.services.finance.credit import service as svc

router = APIRouter()


class CreditProfilePatch(BaseModel):
    date_cible: dt.date | None = None
    nom: str | None = None


class CreditAccountIn(BaseModel):
    institution: str
    produit: str
    limite_actuelle: float
    date_ouverture: dt.date
    derniere_augmentation: dt.date | None = None
    statut: str = "actif"
    notes: str | None = None


class CreditAccountPatch(BaseModel):
    institution: str | None = None
    produit: str | None = None
    limite_actuelle: float | None = None
    date_ouverture: dt.date | None = None
    derniere_augmentation: dt.date | None = None
    statut: str | None = None
    notes: str | None = None


class CreditScoreEntryIn(BaseModel):
    date: dt.date
    score: int
    source: str = ""


class CreditActionRuleIn(BaseModel):
    seuil_score: int
    type: str
    montant_estime: float = 0.0


@router.get("/credit/profile")
def get_credit_profile(session: Session = Depends(get_session)):
    return svc.get_or_create_profile(session).model_dump()


@router.patch("/credit/profile")
def patch_credit_profile(body: CreditProfilePatch, session: Session = Depends(get_session)):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    return svc.update_profile(session, patch).model_dump()


@router.get("/credit/accounts")
def get_credit_accounts(session: Session = Depends(get_session)):
    return [a.model_dump() for a in svc.list_accounts(session)]


@router.post("/credit/accounts", status_code=201)
def create_credit_account(body: CreditAccountIn, session: Session = Depends(get_session)):
    return svc.create_account(session, **body.model_dump()).model_dump()


@router.patch("/credit/accounts/{account_id}")
def patch_credit_account(account_id: int, body: CreditAccountPatch, session: Session = Depends(get_session)):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    account = svc.update_account(session, account_id, patch)
    if not account:
        raise HTTPException(404, f"Compte {account_id} introuvable")
    return account.model_dump()


@router.delete("/credit/accounts/{account_id}", status_code=204)
def delete_credit_account(account_id: int, session: Session = Depends(get_session)):
    if not svc.delete_account(session, account_id):
        raise HTTPException(404, f"Compte {account_id} introuvable")


@router.get("/credit/scores")
def get_credit_scores(session: Session = Depends(get_session)):
    return [s.model_dump() for s in svc.list_score_entries(session)]


@router.post("/credit/scores", status_code=201)
def create_credit_score(body: CreditScoreEntryIn, session: Session = Depends(get_session)):
    return svc.create_score_entry(session, **body.model_dump()).model_dump()


@router.delete("/credit/scores/{entry_id}", status_code=204)
def delete_credit_score(entry_id: int, session: Session = Depends(get_session)):
    if not svc.delete_score_entry(session, entry_id):
        raise HTTPException(404, f"Pointage {entry_id} introuvable")


@router.get("/credit/rules")
def get_credit_rules(session: Session = Depends(get_session)):
    return [r.model_dump() for r in svc.list_rules(session)]


@router.post("/credit/rules", status_code=201)
def create_credit_rule(body: CreditActionRuleIn, session: Session = Depends(get_session)):
    return svc.create_rule(session, **body.model_dump()).model_dump()


@router.delete("/credit/rules/{rule_id}", status_code=204)
def delete_credit_rule(rule_id: int, session: Session = Depends(get_session)):
    if not svc.delete_rule(session, rule_id):
        raise HTTPException(404, f"Règle {rule_id} introuvable")


@router.get("/credit/plan")
def get_credit_plan(session: Session = Depends(get_session)):
    return svc.compute_plan(session)


@router.get("/credit/voyage-budget")
def get_credit_voyage_budget(ordre: str = "desc", session: Session = Depends(get_session)):
    """Budget de voyage finançable en chaînant les cartes actives (une à la
    fois, vidée puis remboursée avant l'échéance -> 0% d'intérêt)."""
    return svc.get_voyage_budget(session, ordre=ordre)
