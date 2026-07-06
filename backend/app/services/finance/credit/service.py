"""Service CRUD + calcul du plan pour le module Marge de crédit (#marge-credit)."""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select

from app.core.timeutil import utcnow
from app.models.credit import CreditAccount, CreditActionRule, CreditProfile, CreditScoreEntry
from app.services.finance.credit.planner import build_plan

DEFAULT_DATE_CIBLE_ANNEES = 3


def get_or_create_profile(session: Session) -> CreditProfile:
    profile = session.exec(select(CreditProfile)).first()
    if profile:
        return profile
    today = dt.date.today()
    profile = CreditProfile(date_cible=today.replace(year=today.year + DEFAULT_DATE_CIBLE_ANNEES))
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


def list_rules(session: Session) -> list[CreditActionRule]:
    return list(session.exec(select(CreditActionRule).order_by(CreditActionRule.seuil_score)).all())


def create_rule(session: Session, **kwargs) -> CreditActionRule:
    rule = CreditActionRule(**kwargs)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def delete_rule(session: Session, rule_id: int) -> bool:
    rule = session.get(CreditActionRule, rule_id)
    if not rule:
        return False
    session.delete(rule)
    session.commit()
    return True


def compute_plan(session: Session) -> dict:
    profile = get_or_create_profile(session)
    accounts = list_accounts(session)
    scores = list_score_entries(session)
    rules = list_rules(session)
    return build_plan(accounts, scores, rules, date_cible=profile.date_cible, today=dt.date.today())
