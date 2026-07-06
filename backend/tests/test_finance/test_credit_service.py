"""Service CRUD + compute_plan pour le module Marge de crédit."""

import datetime as dt

from app.services.finance.credit import service as svc


def test_get_or_create_profile_creates_default_on_first_call(mem_session):
    profile = svc.get_or_create_profile(mem_session)
    assert profile.id is not None
    assert profile.revenu_annuel == 0.0
    # même profil renvoyé au 2e appel (pas de doublon)
    again = svc.get_or_create_profile(mem_session)
    assert again.id == profile.id


def test_update_profile_patches_fields(mem_session):
    svc.get_or_create_profile(mem_session)
    updated = svc.update_profile(mem_session, {"revenu_annuel": 40000.0})
    assert updated.revenu_annuel == 40000.0


def test_account_crud_roundtrip(mem_session):
    account = svc.create_account(
        mem_session, institution="Desjardins", produit="Carte Mastercard",
        limite_actuelle=700, date_ouverture=dt.date(2025, 9, 1),
    )
    assert account.id is not None
    assert svc.list_accounts(mem_session) == [account]

    updated = svc.update_account(mem_session, account.id, {"limite_actuelle": 1200})
    assert updated.limite_actuelle == 1200

    assert svc.update_account(mem_session, 9999, {"limite_actuelle": 1}) is None
    assert svc.delete_account(mem_session, account.id) is True
    assert svc.delete_account(mem_session, account.id) is False
    assert svc.list_accounts(mem_session) == []


def test_score_entry_crud_roundtrip(mem_session):
    entry = svc.create_score_entry(mem_session, date=dt.date(2026, 1, 1), score=650, source="Credit Karma")
    assert entry.id is not None
    assert svc.list_score_entries(mem_session) == [entry]
    assert svc.delete_score_entry(mem_session, entry.id) is True
    assert svc.delete_score_entry(mem_session, entry.id) is False


def test_compute_plan_uses_current_db_state(mem_session):
    svc.update_profile(mem_session, {
        "revenu_annuel": 40000.0,
        "date_arrivee_canada": dt.date(2025, 9, 1),
        "date_cible": dt.date(2025, 12, 1),
    })
    svc.create_account(
        mem_session, institution="Desjardins", produit="Carte Mastercard",
        limite_actuelle=700, date_ouverture=dt.date(2025, 9, 1),
    )
    plan = svc.compute_plan(mem_session)
    assert plan["marge_actuelle"] == 700.0
    assert "projection" in plan and "actions" in plan
