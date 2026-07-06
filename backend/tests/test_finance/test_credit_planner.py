"""Planner marge de crédit : simulation de hausses/ouvertures dans le temps."""

import datetime as dt

from app.models.credit import CreditAccount, CreditProfile, CreditScoreEntry
from app.services.finance.credit.catalog import CreditProduct
from app.services.finance.credit.planner import build_plan


def _profile(date_cible):
    return CreditProfile(revenu_annuel=40000, date_arrivee_canada=dt.date(2025, 9, 1), date_cible=date_cible)


def test_existing_account_gets_increase_after_default_threshold():
    accounts = [
        CreditAccount(
            institution="Desjardins", produit="Carte Mastercard", limite_actuelle=700,
            date_ouverture=dt.date(2025, 9, 1), derniere_augmentation=None, statut="actif",
        )
    ]
    profile = _profile(dt.date(2026, 12, 1))
    plan = build_plan(accounts, [], profile, [], today=dt.date(2026, 7, 1))
    hausses = [a for a in plan["actions"] if a["type"] == "hausse" and a["institution"] == "Desjardins"]
    assert len(hausses) == 1
    assert hausses[0]["date"] == dt.date(2026, 9, 1)  # 12 mois après l'ouverture (règle par défaut)
    assert hausses[0]["delta_limite"] == 350.0  # +50% de 700


def test_new_product_opened_once_eligible():
    catalog = [CreditProduct("Newcomer Bank", "Carte Débutant", "programme_newcomer", 500, 2000, 0, None, 6, 12)]
    profile = _profile(dt.date(2026, 7, 1))
    plan = build_plan([], [], profile, catalog, today=dt.date(2026, 1, 1))
    ouvertures = [a for a in plan["actions"] if a["type"] == "ouverture"]
    assert len(ouvertures) == 1
    assert ouvertures[0]["institution"] == "Newcomer Bank"
    assert ouvertures[0]["date"] == dt.date(2026, 1, 1)  # anciennete_min_mois=0 -> éligible immédiatement


def test_score_gate_blocks_product_requiring_score():
    gated = [CreditProduct("Prime Bank", "Carte Premium", "carte_standard", 3000, 8000, 0, 700, 6, 12)]
    profile = _profile(dt.date(2026, 12, 1))

    plan_no_score = build_plan([], [], profile, gated, today=dt.date(2026, 1, 1))
    assert not [a for a in plan_no_score["actions"] if a["institution"] == "Prime Bank"]

    scores = [CreditScoreEntry(date=dt.date(2026, 1, 1), score=720, source="Test")]
    plan_with_score = build_plan([], scores, profile, gated, today=dt.date(2026, 1, 1))
    assert [a for a in plan_with_score["actions"] if a["institution"] == "Prime Bank"]


def test_anti_inquiry_cooldown_limits_new_accounts_per_window():
    catalog = [
        CreditProduct("Bank A", "Carte A", "programme_newcomer", 500, 1000, 0, None, 6, 12),
        CreditProduct("Bank B", "Carte B", "programme_newcomer", 500, 1000, 0, None, 6, 12),
    ]
    profile = _profile(dt.date(2026, 3, 1))
    plan = build_plan([], [], profile, catalog, today=dt.date(2026, 1, 1))
    ouvertures = [a for a in plan["actions"] if a["type"] == "ouverture"]
    # cooldown anti-inquiry = 4 mois -> une seule ouverture possible sur une fenêtre de 3 mois (jan-mar)
    assert len(ouvertures) == 1


def test_empty_state_still_returns_full_projection():
    profile = _profile(dt.date(2026, 9, 1))
    plan = build_plan([], [], profile, [], today=dt.date(2026, 7, 1))
    assert plan["actions"] == []
    assert len(plan["projection"]) == 3  # juillet, août, septembre 2026
    assert plan["marge_actuelle"] == 0.0
    assert plan["marge_projetee_a_date_cible"] == 0.0
