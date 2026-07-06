"""Service CRUD + calcul du plan pour le module Marge de crédit (#marge-credit)."""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select

from app.core.timeutil import utcnow
from app.models.credit import CreditAccount, CreditProfile, CreditScoreEntry
from app.services.finance.credit.catalog import load_catalog
from app.services.finance.credit.planner import build_plan

DEFAULT_DATE_CIBLE_ANNEES = 3  # par défaut, 3 ans après l'arrivée au Canada


def get_or_create_profile(session: Session) -> CreditProfile:
    profile = session.exec(select(CreditProfile)).first()
    if profile:
        return profile
    today = dt.date.today()
    profile = CreditProfile(
        revenu_annuel=0.0,
        date_arrivee_canada=today,
        date_cible=today.replace(year=today.year + DEFAULT_DATE_CIBLE_ANNEES),
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def update_profile(session: Session, patch: dict) -> CreditProfile:
    profile = get_or_create_profile(session)
    for k, v in patch.items():
        if hasattr(profile, k):
            setattr(profile, k, v)
    profile.updated_at = utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def list_accounts(session: Session) -> list[CreditAccount]:
    return list(session.exec(select(CreditAccount).order_by(CreditAccount.date_ouverture)).all())


def create_account(session: Session, **kwargs) -> CreditAccount:
    account = CreditAccount(**kwargs)
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def update_account(session: Session, account_id: int, patch: dict) -> CreditAccount | None:
    account = session.get(CreditAccount, account_id)
    if not account:
        return None
    for k, v in patch.items():
        if hasattr(account, k):
            setattr(account, k, v)
    account.updated_at = utcnow()
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def delete_account(session: Session, account_id: int) -> bool:
    account = session.get(CreditAccount, account_id)
    if not account:
        return False
    session.delete(account)
    session.commit()
    return True


def list_score_entries(session: Session) -> list[CreditScoreEntry]:
    return list(session.exec(select(CreditScoreEntry).order_by(CreditScoreEntry.date)).all())


def create_score_entry(session: Session, **kwargs) -> CreditScoreEntry:
    entry = CreditScoreEntry(**kwargs)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def delete_score_entry(session: Session, entry_id: int) -> bool:
    entry = session.get(CreditScoreEntry, entry_id)
    if not entry:
        return False
    session.delete(entry)
    session.commit()
    return True


def compute_plan(session: Session) -> dict:
    profile = get_or_create_profile(session)
    accounts = list_accounts(session)
    scores = list_score_entries(session)
    catalog = load_catalog()
    return build_plan(accounts, scores, profile, catalog, today=dt.date.today())
