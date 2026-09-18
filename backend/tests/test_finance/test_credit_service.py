"""Service CRUD + compute_plan pour le module Marge de crédit (v2, règles à seuils)."""

import datetime as dt

from app.services.finance.credit import service as svc


def _add_months(d: dt.date, months: int) -> dt.date:
    total = d.year * 12 + (d.month - 1) + months
    year, month = divmod(total, 12)
    return dt.date(year, month + 1, 1)


def test_get_or_create_profile_creates_default_on_first_call(mem_session):
    profile = svc.get_or_create_profile(mem_session)
    assert profile.id is not None
    again = svc.get_or_create_profile(mem_session)
    assert again.id == profile.id


def test_update_profile_patches_date_cible(mem_session):
    svc.get_or_create_profile(mem_session)
    updated = svc.update_profile(mem_session, {"date_cible": dt.date(2028, 9, 1)})
    assert updated.date_cible == dt.date(2028, 9, 1)


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


def test_rule_crud_roundtrip(mem_session):
    svc.create_rule(mem_session, seuil_score=720, type="hausse", montant_estime=1000)
    rule_bas = svc.create_rule(mem_session, seuil_score=700, type="hausse", montant_estime=500)
    rules = svc.list_rules(mem_session)
    assert [r.seuil_score for r in rules] == [700, 720]  # triées par seuil croissant

    assert svc.delete_rule(mem_session, rule_bas.id) is True
    assert svc.delete_rule(mem_session, rule_bas.id) is False
    assert [r.seuil_score for r in svc.list_rules(mem_session)] == [720]


def test_compute_plan_produces_roadmap_and_growing_projection(mem_session):
    today = dt.date.today()
    six_months_ago = _add_months(today, -6)
    date_cible = _add_months(today, 12)

    svc.update_profile(mem_session, {"date_cible": date_cible})
    svc.create_account(
        mem_session, institution="Desjardins", produit="Carte Mastercard",
        limite_actuelle=700, date_ouverture=dt.date(2025, 9, 1),
    )
    svc.create_score_entry(mem_session, date=six_months_ago, score=650, source="Credit Karma")
    svc.create_score_entry(mem_session, date=today, score=680, source="Credit Karma")
    svc.create_rule(mem_session, seuil_score=685, type="hausse", montant_estime=1000)

    plan = svc.compute_plan(mem_session)
    assert plan["projection_possible"] is True
    assert len(plan["projection_score"]) > 1
    assert len(plan["actions"]) >= 1
    assert plan["actions"][0]["type"] == "hausse"
